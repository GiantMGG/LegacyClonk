/*
 * LegacyClonk
 *
 * Copyright (c) 2026, The LegacyClonk Team and contributors
 *
 * Distributed under the terms of the ISC license; see accompanying file
 * "COPYING" for details.
 *
 * "Clonk" is a registered trademark of Matthes Bender, used with permission.
 * See accompanying file "TRADEMARK" for details.
 *
 * To redistribute this file separately, substitute the full license texts
 * for the above references.
 */

// Diagnostic scene shot (spec playtest-vision-tier2 §2C): CPU-composes a
// PNG of the current landscape/view and writes a SceneTruth JSON sidecar.
// Console-safe — no GUI includes; all pixel reads go through the CPU
// accessors (C4Surface::GetPixDw is RAM-backed for non-primary surfaces).
//
// Probe corrections applied (Task 1 findings, supersede plan wording):
//  - StdBitmap is B8G8R8 here → SetPixel24, never SetPixel32 (the P3 heap
//    overrun trap).
//  - C4Landscape::Surface32 is protected → read via the public
//    Landscape._GetPixDw(x, y, fApplyModulation) accessor; dims via
//    Landscape.Width/Height with clamping.
//  - Engine u32 layout is byte0=B (C4RGB(r,g,b) = r<<16|g<<8|b); both
//    SetPixel24 and CPNGFile's png_set_bgr preserve that order, so raw
//    accessor values and C4RGB-built colors land in the PNG as-is.
//  - CPNGFile ctor throws std::runtime_error on fopen failure: the
//    construct+encode is wrapped so the unwritable-path edge (spec §4.5)
//    stays a plain "log + return false", never a crash.
//  - Facet source rect (P2): (Face.X + iPhase*Face.Wdt,
//    Face.Y + DrawDir*Face.Hgt, Face.Wdt, Face.Hgt) with iPhase reversed
//    for Reverse actions; idle objects use the DrawFace top-left
//    Shape-size rect (C4Object::DrawFace straight-blit geometry).

#include "C4Game.h"
#include "C4Object.h"
#include "C4Player.h"
#include "C4Id.h"
#include "StdColors.h"
#include "StdBitmap.h"
#include "StdPNG.h"

#include <algorithm>
#include <format>
#include <fstream>
#include <stdexcept>
#include <string>

namespace
{
	// JSON string-content escaping for the sidecar, so def/player/action
	// names cannot break the document.
	std::string JsonString(const char *sz)
	{
		if (!sz) return "\"\"";
		std::string out;
		out.reserve(std::strlen(sz) + 2);
		out += '"';
		for (const char *p = sz; *p; ++p)
		{
			const unsigned char c = static_cast<unsigned char>(*p);
			switch (c)
			{
			case '"':  out += "\\\""; break;
			case '\\': out += "\\\\"; break;
			default:
				if (c < 0x20)
					out += std::format("\\u{:04x}", c);
				else
					out += static_cast<char>(c);
				break;
			}
		}
		out += '"';
		return out;
	}

	// Integer alpha-average for facet blits into the shot buffer — mirrors
	// C4Surface::BltAlpha (StdColors.h) with no floating point anywhere.
	// The alpha byte runs inverted as in the engine surface layout:
	// 0 = fully opaque, 255 = fully transparent.
	std::uint32_t BlendPixel(std::uint32_t dst, std::uint32_t src)
	{
		const std::uint32_t alpha = src >> 24; // transparency weight
		if (alpha >= 0xf0) return dst;          // (near-)transparent: keep dst
		if (alpha == 0) return src;             // fully opaque: overwrite
		const std::uint32_t invAlpha = 255 - alpha;
		const std::uint32_t r = (((src >> 16) & 0xff) * invAlpha + ((dst >> 16) & 0xff) * alpha) >> 8;
		const std::uint32_t g = (((src >> 8) & 0xff) * invAlpha + ((dst >> 8) & 0xff) * alpha) >> 8;
		const std::uint32_t b = ((src & 0xff) * invAlpha + (dst & 0xff) * alpha) >> 8;
		return C4RGB(r, g, b);
	}

	// CPU facet blit into the B8G8R8 shot bitmap. Source pixels come from
	// the def graphics sheet (RAM-backed, headless-safe per probe P1/P3).
	void BlitFacet(StdBitmap &shot, C4Surface *pSheet, int32_t iDstX, int32_t iDstY,
		int32_t iSrcX, int32_t iSrcY, int32_t iWdt, int32_t iHgt)
	{
		if (!pSheet || !iWdt || !iHgt) return;
		const int32_t sheetWdt = pSheet->Wdt, sheetHgt = pSheet->Hgt;
		const int32_t shotWdt = static_cast<int32_t>(shot.GetWidth());
		const int32_t shotHgt = static_cast<int32_t>(shot.GetHeight());
		for (int32_t y = 0; y < iHgt; ++y)
		{
			const int32_t sy = iSrcY + y, dy = iDstY + y;
			if (sy < 0 || sy >= sheetHgt || dy < 0 || dy >= shotHgt) continue;
			for (int32_t x = 0; x < iWdt; ++x)
			{
				const int32_t sx = iSrcX + x, dx = iDstX + x;
				if (sx < 0 || sx >= sheetWdt || dx < 0 || dx >= shotWdt) continue;
				const std::uint32_t srcPix = pSheet->GetPixDw(sx, sy, true);
				shot.SetPixel24(dx, dy, BlendPixel(shot.GetPixel24(dx, dy), srcPix));
			}
		}
	}
} // namespace

bool CSceneShot::ComposeAndWrite(const char *szPath, int32_t iWdt, int32_t iHgt)
{
	// Spec §4.5 failure semantics: every failure path is "log + continue"
	// in the fire site; we just report failure here.
	if (!szPath || !szPath[0] || iWdt <= 0 || iHgt <= 0) return false;

	// The main (first) section owns the composed landscape. Probe P1:
	// Landscape.Width/Height are MapWidth/MapHeight * MapZoom (pixel space).
	const auto &sections = Game.GetAllSections();
	if (sections.empty()) return false;
	C4Section &section = *sections.front();
	C4Landscape &land = section.Landscape;
	const int32_t landWdt = std::max(land.Width, 1);
	const int32_t landHgt = std::max(land.Height, 1);

	// Camera anchor: first player with a maintained ViewX/ViewY (updated
	// headless by C4Player::UpdateView); world-center fallback otherwise.
	int32_t camX, camY;
	const char *szCamSrc;
	const C4Player *pCamPlr = nullptr;
	for (const C4Player *pPlr = Game.Players.First; pPlr; pPlr = pPlr->Next)
	{
		if (pPlr->ViewX || pPlr->ViewY)
		{
			pCamPlr = pPlr;
			break;
		}
	}
	if (pCamPlr)
	{
		camX = pCamPlr->ViewX;
		camY = pCamPlr->ViewY;
		szCamSrc = "player";
	}
	else
	{
		camX = landWdt / 2;
		camY = landHgt / 2;
		szCamSrc = "center";
	}

	// Desired view rect, centered on the anchor, clipped to the landscape.
	// Where the world is smaller than the shot (spec §4.4) the out-of-range
	// band keeps its sky fill — the letterbox.
	const int32_t vx0 = camX - iWdt / 2, vy0 = camY - iHgt / 2;
	const int32_t rectX = std::max(vx0, 0), rectY = std::max(vy0, 0);
	const int32_t rectWdt = std::max(std::min(vx0 + iWdt, landWdt) - rectX, 0);
	const int32_t rectHgt = std::max(std::min(vy0 + iHgt, landHgt) - rectY, 0);
	const bool fLandscape = section.LandscapeLoaded && rectWdt > 0 && rectHgt > 0;

	StdBitmap shot(static_cast<std::uint32_t>(iWdt), static_cast<std::uint32_t>(iHgt), false);

	// Layer 1: sky rows per world-Y. GetSkyFadeClr is integer-only and
	// flattens automatically when the scenario gradient is disabled
	// (FadeClr1 == FadeClr2, incl. sky-image scenarios). The lookup is
	// clamped to the world so letterbox rows below the landscape cannot hit
	// the integer-wrap edge of the fade math.
	for (int32_t sy = 0; sy < iHgt; ++sy)
	{
		const std::uint32_t skyClr = land.Sky.GetSkyFadeClr(std::clamp(vy0 + sy, 0, landHgt - 1));
		for (int32_t sx = 0; sx < iWdt; ++sx)
		{
			shot.SetPixel24(sx, sy, skyClr);
		}
	}

	// Layer 2: landscape region, pixel-exact copy of the CPU-rasterized
	// Surface32 through the public accessor (probe correction, P1).
	if (fLandscape)
	{
		for (int32_t sy = 0; sy < rectHgt; ++sy)
		{
			for (int32_t sx = 0; sx < rectWdt; ++sx)
			{
				shot.SetPixel24(rectX - vx0 + sx, rectY - vy0 + sy,
					land._GetPixDw(rectX + sx, rectY + sy, false));
			}
		}
	}

	// Layer 3: objects whose shape center lies inside the view rect, drawn
	// in list order. The sidecar object list (P5 key set) is filled here so
	// ground truth and pixels always describe the same in-view set.
	std::string objectsJson = "[";
	int32_t iObjCount = 0;
	for (C4Object *pObj : Game.GetAllObjects())
	{
		if (!pObj || pObj->Status != C4OS_NORMAL || !pObj->Def) continue;
		const int32_t shapeCx = pObj->x + pObj->Shape.x + pObj->Shape.Wdt / 2;
		const int32_t shapeCy = pObj->y + pObj->Shape.y + pObj->Shape.Hgt / 2;
		if (shapeCx < rectX || shapeCx >= rectX + rectWdt
		 || shapeCy < rectY || shapeCy >= rectY + rectHgt) continue;

		if (iObjCount) objectsJson += ',';
		objectsJson += std::format("{{\"number\":{},\"def_id\":{},\"def_name\":{},\"x\":{},\"y\":{},\"color\":{}",
			pObj->Number, JsonString(C4IdText(pObj->Def->id)), JsonString(pObj->Def->GetName()),
			pObj->x, pObj->y, pObj->Color);
		objectsJson += std::format(",\"in_material\":{},\"action_name\":{}}}",
			JsonString(pObj->Section && pObj->Section->MatValid(pObj->InMat)
				? pObj->Section->Material.Map[pObj->InMat].Name : ""),
			JsonString(pObj->Action.Name));
		++iObjCount;

		// Sprite source + placement (P2 formula; documented corners: no
		// horizontal mirror for FlipDir, full-Con only, no def scale < 1).
		const int32_t shapeX = pObj->x + pObj->Shape.x - vx0;
		const int32_t shapeY = pObj->y + pObj->Shape.y - vy0;
		const bool bActiveAction = pObj->Action.Act > ActIdle && pObj->Action.Act < pObj->Def->ActNum;
		const bool bUsableFacet = pObj->Action.Facet.Surface
			&& pObj->Action.Facet.Wdt > 0 && pObj->Action.Facet.Hgt > 0;
		C4Surface *pSheet = pObj->GetGraphics() ? pObj->GetGraphics()->GetBitmap(pObj->Color) : nullptr;
		if (bActiveAction && pObj->GetCon() == FullCon && bUsableFacet)
		{
			int32_t iPhase = pObj->Action.Phase;
			const C4ActionDef &actDef = pObj->Def->ActMap[pObj->Action.Act];
			if (actDef.Reverse) iPhase = actDef.Length - 1 - iPhase;
			BlitFacet(shot, pObj->Action.Facet.Surface,
				shapeX + pObj->Action.FacetX, shapeY + pObj->Action.FacetY,
				pObj->Action.Facet.X + iPhase * pObj->Action.Facet.Wdt,
				pObj->Action.Facet.Y + pObj->Action.DrawDir * pObj->Action.Facet.Hgt,
				pObj->Action.Facet.Wdt, pObj->Action.Facet.Hgt);
		}
		else if (!bActiveAction && pSheet
			&& pObj->Def->Shape.Wdt > 0 && pObj->Def->Shape.Hgt > 0)
		{
			// Idle: DrawFace straight-blit geometry (top-left Shape-size
			// rect of the def sheet, C4Object::DrawFace).
			BlitFacet(shot, pSheet, shapeX, shapeY,
				0, 0, pObj->Def->Shape.Wdt, pObj->Def->Shape.Hgt);
		}
		else
		{
			// Unusable sprite — nothing silently disappears: solid square in
			// the object color, size clamped to 4..16 px, on the shape center.
			const int32_t sq = std::clamp(std::min(pObj->Shape.Wdt, pObj->Shape.Hgt), 4, 16);
			for (int32_t y = 0; y < sq; ++y)
			{
				const int32_t dy = shapeY + pObj->Shape.Hgt / 2 - sq / 2 + y;
				if (dy < 0 || dy >= iHgt) continue;
				for (int32_t x = 0; x < sq; ++x)
				{
					const int32_t dx = shapeX + pObj->Shape.Wdt / 2 - sq / 2 + x;
					if (dx < 0 || dx >= iWdt) continue;
					shot.SetPixel24(dx, dy, pObj->Color | 0xff000000U);
				}
			}
		}
	}
	objectsJson += ']';

	// SceneTruth sidecar (P5 key set verbatim, spec §1).
	std::string playersJson = "[";
	int32_t iPlrCount = 0;
	for (const C4Player *pPlr = Game.Players.First; pPlr; pPlr = pPlr->Next)
	{
		if (iPlrCount) playersJson += ',';
		playersJson += std::format("{{\"number\":{},\"name\":{},\"color\":{},\"x\":{},\"y\":{}}}",
			pPlr->Number, JsonString(pPlr->GetName()), pPlr->ColorDw, pPlr->ViewX, pPlr->ViewY);
		++iPlrCount;
	}
	playersJson += ']';

	const std::string json = std::format(
		"{{\"tick\":{},\"frame_counter\":{},\"view\":{{\"x\":{},\"y\":{},\"wdt\":{},\"hgt\":{}}},\"camera_source\":{},\"players\":{},\"objects\":{},\"capture\":{}}}",
		Game.FrameCounter, Game.FrameCounter,
		rectX, rectY, rectWdt, rectHgt,
		JsonString(szCamSrc), playersJson, objectsJson,
		JsonString(fLandscape ? "ok" : "no_landscape"));

	// Encode + sidecar. The PNG encoder throws std::runtime_error on fopen
	// failure — wrap so the unwritable-path edge stays non-fatal (spec §4.5).
	try
	{
		CPNGFile{std::string(szPath), static_cast<std::uint32_t>(iWdt), static_cast<std::uint32_t>(iHgt), false}.Encode(shot.GetBytes());
	}
	catch (const std::runtime_error &)
	{
		return false; // fire site logs the write-failure line; run continues
	}

	std::string sidecarPath(szPath);
	const std::string::size_type dot = sidecarPath.find_last_of('.');
	const std::string::size_type slash = sidecarPath.find_last_of("/\\");
	if (dot != std::string::npos && (slash == std::string::npos || dot > slash))
	{
		sidecarPath.resize(dot);
	}
	sidecarPath += ".json";
	if (std::ofstream out{sidecarPath, std::ios::binary}; out)
	{
		out << json;
		return out.good();
	}
	return false;
}

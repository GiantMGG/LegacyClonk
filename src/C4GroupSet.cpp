/*
 * LegacyClonk
 *
 * Copyright (c) RedWolf Design
 * Copyright (c) 2001, Sven2
 * Copyright (c) 2017-2024, The LegacyClonk Team and contributors
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

// a set of group files
// manages system file overwriting by scearios or folders

#include <C4GroupSet.h>

#ifndef USE_CONSOLE
#include <C4Game.h>
#else
#include "C4Components.h"
#include "C4Group.h"
#endif

#include <C4Log.h>
#include "C4ResStrTable.h"

#include <cstring>

C4GroupSetNode::C4GroupSetNode(C4GroupSet &rParent, C4GroupSetNode *pPrev, C4Group &rGroup, bool fGrpOwned, int32_t id)
{
	// set parent
	pParent = &rParent;
	// link into list
	this->pPrev = pPrev;
	if (pPrev) { pNext = pPrev->pNext; pPrev->pNext = this; }
	else { pNext = pParent->pFirst; pParent->pFirst = this; }
	if (pNext) pNext->pPrev = this; else pParent->pLast = this;
	// set group
	pGroup = &rGroup;
	this->fGrpOwned = fGrpOwned;
	// set id
	this->id = id;
}

C4GroupSetNode::~C4GroupSetNode()
{
	// remove group
	if (fGrpOwned) delete pGroup;
	// unlink from list
	(pPrev ? pPrev->pNext : pParent->pFirst) = pNext;
	(pNext ? pNext->pPrev : pParent->pLast) = pPrev;
}

void C4GroupSet::Clear()
{
	// clear nodes
	while (pFirst) delete pFirst;
	pFirst = nullptr;
}

void C4GroupSet::Default()
{
	// zero fields
	pFirst = pLast = nullptr;
	// do not reset index here, because group set IDs are meant to be unique
	// for each instance of the engine
	// see also C4GraphicsResource::RegisterGlobalGraphics
}

C4GroupSet::C4GroupSet()
{
	// zero fields
	Default();
	iIndex = 0;
}

C4GroupSet::~C4GroupSet()
{
	// clear nodes
	Clear();
}

bool C4GroupSet::RegisterGroup(C4Group &rGroup, bool fOwnGrp, int32_t Priority, int32_t Contents, bool fCheckContent)
{
	// get node to sort in
	// begin at back end and search for higher priority
	C4GroupSetNode *pNode;
	for (pNode = pLast; pNode; pNode = pNode->pPrev)
		if (pNode->Priority > Priority) break;
	// create new node
	C4GroupSetNode *pNewNode = new C4GroupSetNode(*this, pNode, rGroup, fOwnGrp, ++iIndex);
	// check content
	if (fCheckContent) Contents = CheckGroupContents(rGroup, Contents);
	// set priority and contents mask
	pNewNode->Priority = Priority;
	pNewNode->Contents = Contents;

#ifndef USE_CONSOLE
	// always add fonts directly
	if (Contents & C4GSCnt_FontDefs)
		Game.FontLoader.LoadDefs(rGroup, Config);
#endif

	// success
	return true;
}

int32_t C4GroupSet::CheckGroupContents(C4Group &rGroup, int32_t Contents)
{
	// update mask
	if (Contents & C4GSCnt_Graphics) if (!rGroup.FindEntry(C4CFN_Graphics)) Contents = Contents & ~C4GSCnt_Graphics;
	if (Contents & C4GSCnt_Loaders)
	{
		if (!rGroup.FindEntry("Loader*.bmp")
			&& !rGroup.FindEntry("Loader*.png")
			&& !rGroup.FindEntry("Loader*.jpg")
			&& !rGroup.FindEntry("Loader*.jpeg"))
		{
			Contents = Contents & ~C4GSCnt_Loaders;
		}
	}
	if (Contents & C4GSCnt_Material) if (!rGroup.FindEntry(C4CFN_Material)) Contents = Contents & ~C4GSCnt_Material;
	if (Contents & C4GSCnt_Music) if (!rGroup.FindEntry(C4CFN_Music)) Contents = Contents & ~C4GSCnt_Music;
	if (Contents & C4GSCnt_Definitions) if (!rGroup.FindEntry(C4CFN_DefFiles)) Contents = Contents & ~C4GSCnt_Definitions;
	if (Contents & C4GSCnt_FontDefs) if (!rGroup.FindEntry(C4CFN_FontFiles)) if (!rGroup.FindEntry(C4CFN_FontDefs)) Contents = Contents & ~C4GSCnt_FontDefs;
	// return it
	return Contents;
}

bool C4GroupSet::RegisterGroups(C4GroupSet &rCopy, int32_t Contents, const char *szFilename, int32_t iMaxSkipID)
{
	// get all groups of rCopy
	int32_t Contents2;
	for (C4GroupSetNode *pNode = rCopy.pFirst; pNode; pNode = pNode->pNext)
	{
		if ((Contents2 = pNode->Contents & Contents))
		{
			if (pNode->id > iMaxSkipID)
			{
				if (!szFilename)
				{
					// add group but don't check the content again!
					RegisterGroup(*pNode->pGroup, false, pNode->Priority, Contents2, false);
				}
				else
				{
					// if a filename is given, open the child group
					C4Group *pGroup = new C4Group();
					if (!pGroup->OpenAsChild(pNode->pGroup, szFilename))
					{
						delete pGroup; continue;
					}
					// add the child group to the local list; contents equal Contents2
					// but this flag is not likely to be used
					if (!RegisterGroup(*pGroup, true, pNode->Priority, Contents2, false))
						delete pGroup;
				}
			}
		}
	}
	// done, success
	return true;
}

C4Group *C4GroupSet::FindGroup(int32_t Contents, C4Group *pAfter, bool fSamePrio)
{
	// get priority
	int32_t iPriority = -1;
	// find group by matching content mask
	for (C4GroupSetNode *pNode = pFirst; pNode; pNode = pNode->pNext)
	{
		// check contents
		if (!pAfter && (pNode->Contents & Contents))
			// check priority
			if (iPriority == -1 || iPriority == pNode->Priority)
				// success, found an entry
				return pNode->pGroup;
		// find next clear flag
		if (pNode->pGroup == pAfter) { pAfter = nullptr; if (fSamePrio) iPriority = pNode->Priority; }
	}
	// nothing found
	return nullptr;
}

C4Group *C4GroupSet::FindEntry(const char *szWildcard, int32_t *pPriority, int32_t *pID)
{
	// find group that has this entry
	for (C4GroupSetNode *pNode = pFirst; pNode; pNode = pNode->pNext)
		if (pNode->pGroup->FindEntry(szWildcard))
		{
			// assign priority and ID, if ptrs is given
			if (pPriority) *pPriority = pNode->Priority;
			if (pID) *pID = pNode->id;
			// return found group
			return pNode->pGroup;
		}
	// nothing found
	return nullptr;
}

bool C4GroupSet::LoadEntryString(const char *szEntryName, StdStrBuf &rBuf)
{
	// Load the entry from the first group that has it
	C4Group *pGroup;
	if ((pGroup = FindEntry(szEntryName)))
		return pGroup->LoadEntryString(szEntryName, rBuf);
	// Didn't find it
	return false;
}

bool C4GroupSet::CloseFolders()
{
	// close everything that has folder-priority
	for (C4GroupSetNode *pNode = pFirst, *pNext; pNode; pNode = pNext)
	{
		// get next, as pNode might be destroyed
		pNext = pNode->pNext;
		// check if priority matches
		if (Inside<int32_t>(pNode->Priority, C4GSPrio_Folder, C4GSPrio_Folder2) || pNode->Priority == C4GSPrio_Scenario)
			// clear it!
			delete pNode;
	}
	// done, success
	return true;
}

C4Group *C4GroupSet::GetGroup(int32_t iIndex)
{
	// Invalid index
	if (iIndex < 0)
		return nullptr;
	// Find indicated group
	for (C4GroupSetNode *pNode = pFirst; pNode; pNode = pNode->pNext)
		if (iIndex == 0)
			return pNode->pGroup;
		else
			iIndex--;
	// Indicated group not found
	return nullptr;
}

C4Group **C4GroupSet::GetGroupPtr(std::int32_t index)
{
	// Invalid index
	if (index < 0)
		return nullptr;
	// Find indicated group
	for (C4GroupSetNode *pNode = pFirst; pNode; pNode = pNode->pNext)
		if (index == 0)
			return &pNode->pGroup;
		else
			index--;
	// Indicated group not found
	return nullptr;
}

C4Group *C4GroupSet::RegisterParentFolders(const char *szScenFilename)
{
	// the scenario filename may be a scenario or directly a group folder
	C4Group *pParentGroup = nullptr; bool fParentC4F;
	char szParentfolder[_MAX_PATH + 1];
	if (SEqualNoCase(GetExtension(szScenFilename), "c4f"))
	{
		fParentC4F = true;
		SCopy(szScenFilename, szParentfolder, _MAX_PATH);
	}
	else
	{
		GetParentPath(szScenFilename, szParentfolder);
		fParentC4F = SEqualNoCase(GetExtension(szParentfolder), "c4f");
	}
	if (fParentC4F)
	{
		// Cycle-246 UB hardening (engine-ub-hardening): the previous code
		// NUL-patched the path separators of this stack buffer in place and
		// then ran SLen()/GetExtension() across the patched bytes, so a read
		// could pass the terminator the patch itself had clobbered
		// (build-divergent stack-UB; cycle-172/173 note). The walk below
		// derives the same segment layout from indices and never mutates the
		// buffer: a separator is any of '/' and DirectorySeparator, a segment
		// is a maximal separator-free run, and extension checks run on
		// bounded per-segment copies.
		const size_t iLen = SLen(szParentfolder);
		const auto fIsSep = [](char c) { return c == DirectorySeparator || c == '/'; };
		char szSeg[_MAX_PATH + 1];

		// Pass 1 — walk segments from the last one upward while their
		// extension is .c4f (the old back-trace). iSegEnd is the exclusive
		// end of the segment under examination. iAboveEnd remembers the end
		// of the most recent .c4f segment seen; the joined prefix (old
		// restore mode) runs from the buffer start to the end of the first
		// .c4f ancestor of the first non-.c4f segment.
		size_t iSegEnd = iLen;
		while (iSegEnd > 0 && fIsSep(szParentfolder[iSegEnd - 1])) --iSegEnd; // trailing separators
		size_t iAboveEnd = iLen;
		bool fPerSegment = true; // per-segment opening unless an interior non-.c4f segment breaks the walk
		for (;;)
		{
			if (iSegEnd == 0) break; // every segment was .c4f
			size_t iSegStart = iSegEnd;
			while (iSegStart > 0 && !fIsSep(szParentfolder[iSegStart - 1]))
				--iSegStart;
			const size_t iSegLen = iSegEnd - iSegStart;
			std::memcpy(szSeg, szParentfolder + iSegStart, iSegLen);
			szSeg[iSegLen] = '\0';
			if (!SEqualNoCase(GetExtension(szSeg), "c4f", 3))
			{
				// Non-.c4f segment breaks the walk. Old behavior: if only
				// separators precede it, the back-trace had reached the string
				// start and every segment opened individually; otherwise the
				// path up to the first .c4f ancestor joined into one prefix
				// group with the remaining .c4f ancestors as its children.
				size_t iPrev = iSegStart;
				while (iPrev > 0 && fIsSep(szParentfolder[iPrev - 1]))
					--iPrev;
				fPerSegment = (iPrev == 0);
				break;
			}
			// .c4f segment: remember its end, continue with the previous segment
			iAboveEnd = iSegEnd;
			iSegEnd = iSegStart;
			while (iSegEnd > 0 && fIsSep(szParentfolder[iSegEnd - 1]))
				--iSegEnd;
		}

		int32_t iGroupIndex = 0;
		if (fPerSegment)
		{
			// Old forward walk: every segment opens, the first via Open, the
			// rest as children of the previous one.
			size_t iPos = 0;
			while (iPos < iLen)
			{
				while (iPos < iLen && fIsSep(szParentfolder[iPos])) ++iPos; // skip separators
				if (iPos >= iLen) break;
				size_t iTo = iPos;
				while (iTo < iLen && !fIsSep(szParentfolder[iTo])) ++iTo;
				const size_t iSegLen = iTo - iPos;
				std::memcpy(szSeg, szParentfolder + iPos, iSegLen);
				szSeg[iSegLen] = '\0';
				// open this folder
				C4Group *pGroup = new C4Group();
				if (pParentGroup)
				{
					if (!pGroup->OpenAsChild(pParentGroup, szSeg))
					{
						LogFatalNTr("{}: {}", LoadResStr(C4ResStrTableKey::IDS_PRC_FILENOTFOUND), szSeg);
						delete pGroup; return nullptr;
					}
				}
				else if (!pGroup->Open(szSeg))
				{
					LogFatalNTr("{}: {}", LoadResStr(C4ResStrTableKey::IDS_PRC_FILENOTFOUND), szSeg);
					delete pGroup; return nullptr;
				}
				// set this group as new parent
				pParentGroup = pGroup;
				// add to group set, if this is a true scenario folder
				int32_t iContentsMask;
				if (WildcardMatch(C4CFN_FolderFiles, pParentGroup->GetName()))
					iContentsMask = C4GSCnt_Folder;
				else
					iContentsMask = C4GSCnt_Directory;
				if (!RegisterGroup(*pParentGroup, true, C4GSPrio_Folder + iGroupIndex++, iContentsMask))
				{
					delete pParentGroup; LogFatalNTr("RegGrp: internal error"); return nullptr;
				}
				iPos = iTo;
			}
		}
		else
		{
			// Old restore mode: the joined prefix (buffer start up to the
			// first .c4f ancestor of the breaking segment) opens as one
			// group, then each remaining .c4f ancestor opens as its child.
			const size_t iPrefixEnd = iAboveEnd;
			std::memcpy(szSeg, szParentfolder, iPrefixEnd);
			szSeg[iPrefixEnd] = '\0';
			C4Group *pGroup = new C4Group();
			if (!pGroup->Open(szSeg))
			{
				LogFatalNTr("{}: {}", LoadResStr(C4ResStrTableKey::IDS_PRC_FILENOTFOUND), szSeg);
				delete pGroup; return nullptr;
			}
			pParentGroup = pGroup;
			int32_t iContentsMask;
			if (WildcardMatch(C4CFN_FolderFiles, pParentGroup->GetName()))
				iContentsMask = C4GSCnt_Folder;
			else
				iContentsMask = C4GSCnt_Directory;
			if (!RegisterGroup(*pParentGroup, true, C4GSPrio_Folder + iGroupIndex++, iContentsMask))
			{
				delete pParentGroup; LogFatalNTr("RegGrp: internal error"); return nullptr;
			}
			size_t iPos = iPrefixEnd;
			while (iPos < iLen)
			{
				while (iPos < iLen && fIsSep(szParentfolder[iPos])) ++iPos;
				if (iPos >= iLen) break;
				size_t iTo = iPos;
				while (iTo < iLen && !fIsSep(szParentfolder[iTo])) ++iTo;
				const size_t iSegLen = iTo - iPos;
				std::memcpy(szSeg, szParentfolder + iPos, iSegLen);
				szSeg[iSegLen] = '\0';
				C4Group *pGroup = new C4Group();
				if (!pGroup->OpenAsChild(pParentGroup, szSeg))
				{
					LogFatalNTr("{}: {}", LoadResStr(C4ResStrTableKey::IDS_PRC_FILENOTFOUND), szSeg);
					delete pGroup; return nullptr;
				}
				pParentGroup = pGroup;
				int32_t iContentsMask;
				if (WildcardMatch(C4CFN_FolderFiles, pParentGroup->GetName()))
					iContentsMask = C4GSCnt_Folder;
				else
					iContentsMask = C4GSCnt_Directory;
				if (!RegisterGroup(*pParentGroup, true, C4GSPrio_Folder + iGroupIndex++, iContentsMask))
				{
					delete pParentGroup; LogFatalNTr("RegGrp: internal error"); return nullptr;
				}
				iPos = iTo;
			}
		}
	}
	return pParentGroup;
}

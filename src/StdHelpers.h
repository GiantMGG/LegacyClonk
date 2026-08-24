/*
 * LegacyClonk
 *
 * Copyright (c) 2020-2023, The LegacyClonk Team and contributors
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

#pragma once

#include <concepts>
#include <cstddef>
#include <functional>
#include <iterator>
#include <limits>
#include <memory>
#include <stdexcept>
#include <type_traits>
#include <utility>

template<std::integral To, std::integral From>
To checked_cast(From from)
{
	if constexpr (std::is_signed_v<From>)
	{
		if constexpr (std::is_unsigned_v<To>)
		{
			if (from < 0)
			{
				throw std::runtime_error{"Conversion of negative value to unsigned type requested"};
			}
		}
		else if constexpr (std::numeric_limits<From>::min() < std::numeric_limits<To>::min())
		{
			if (from < std::numeric_limits<To>::min())
			{
				throw std::runtime_error{"Conversion of value requested that is smaller than the target-type minimum"};
			}
		}
	}

	if constexpr (std::numeric_limits<From>::max() > std::numeric_limits<To>::max())
	{
		if (std::cmp_greater(from, std::numeric_limits<To>::max()))
		{
			throw std::runtime_error{"Conversion of value requested that is bigger than the target-type maximum"};
		}
	}

	return static_cast<To>(from);
}

template<std::integral T>
constexpr T RoundedDivision(T numerator, T denominator) noexcept
{
	return (numerator + denominator / 2) / denominator;
}

template<typename... T>
class StdOverloadedCallable : public T...
{
public:
	using T::operator()...;
};

namespace detail
{
	template <typename Function>
	struct FunctionSingleArgument_s;

	template <typename Return, typename Argument>
	struct FunctionSingleArgument_s<Return(*)(Argument)>
	{
		using type = Argument;
	};

	template <auto function>
	using FunctionSingleArgument = typename FunctionSingleArgument_s<decltype(function)>::type;
}

template <auto function>
struct C4SingleArgumentFunctionFunctor
{
	using Arg = detail::FunctionSingleArgument<function>;

	void operator()(Arg arg)
	{
		std::invoke(function, std::forward<Arg>(arg));
	}
};

template <auto free>
using C4DeleterFunctionUniquePtr = std::unique_ptr<std::remove_pointer_t<detail::FunctionSingleArgument<free>>, C4SingleArgumentFunctionFunctor<free>>;


namespace detail
{
	template<typename T>
	struct PointerToMember;

	template<typename F, typename C>
	struct PointerToMember<F C::*>
	{
		using FieldType = F;
		using ClassType = C;
	};
}

template<auto Member>
class C4LinkedListIterator
{
public:
	using iterator_category = std::forward_iterator_tag;
	using value_type = typename detail::PointerToMember<decltype(Member)>::ClassType;
	using difference_type = std::ptrdiff_t;
	using pointer = value_type *;
	using reference = value_type &;

public:
	C4LinkedListIterator(const pointer value = nullptr) noexcept : value{value} {}

public:
	C4LinkedListIterator &operator++() noexcept { value = value->*Member; return *this; }
	C4LinkedListIterator operator++(int) noexcept { C4LinkedListIterator iterator{*this}; ++(*this); return iterator; }

	bool operator==(const C4LinkedListIterator &other) const noexcept { return value == other.value; }
	bool operator==(std::default_sentinel_t) const noexcept { return !value; }

	reference operator*() const noexcept { return *value; }
	pointer operator->() const noexcept { return value; }

private:
	pointer value;
};

template<auto Member>
[[nodiscard]] inline C4LinkedListIterator<Member> begin(const C4LinkedListIterator<Member> iter) noexcept
{
	return iter;
}

template<auto Member>
[[nodiscard]] inline C4LinkedListIterator<Member> end(const C4LinkedListIterator<Member>) noexcept
{
	return {};
}

// based on boost container_hash's hashCombine
constexpr std::size_t hashCombine(std::size_t hash, std::size_t nextHash)
{
	if constexpr (sizeof(std::size_t) == 4)
	{
		constexpr std::size_t c1 = 0xcc9e2d51;
		constexpr std::size_t c2 = 0x1b873593;

		nextHash *= c1;
		nextHash = std::rotl(nextHash, 15);
		nextHash *= c2;

		hash ^= nextHash;
		hash = std::rotl(hash, 13);
		hash = hash * 5 + 0xe6546b64;
	}
	else if constexpr (sizeof(std::size_t) == 8)
	{
		constexpr std::size_t m = 0xc6a4a7935bd1e995;
		constexpr int r = 47;

		nextHash *= m;
		nextHash ^= nextHash >> r;
		nextHash *= m;

		hash ^= nextHash;
		hash *= m;

		// Completely arbitrary number, to prevent 0's
		// from hashing to 0.
		hash += 0xe6546b64;
	}
	else
	{
		hash ^= nextHash + 0x9e3779b9 + (hash << 6) + (hash >> 2);
	}
	return hash;
}

template<typename... Args>
constexpr void HashCombineArguments(std::size_t &hash, Args &&...args)
{
	(..., (hash = hashCombine(hash, std::hash<std::decay_t<Args>>{}(args))));
}

template<typename... Args>
constexpr std::size_t HashArguments(Args &&...args)
{
	std::size_t result{0};
	(..., (result = hashCombine(result, std::hash<std::decay_t<Args>>{}(args))));
	return result;
}

struct C4TransparentHash
{
	using is_transparent = void;

	template<typename T>
	std::size_t operator()(const T &t) const noexcept(noexcept(std::hash<T>{}(t)))
	{
		return std::hash<T>{}(t);
	}
};

template<typename Enum> requires std::is_enum_v<Enum>
struct C4BitfieldOperators : std::false_type {};

template<typename Enum>
concept C4BitfieldOperatorsEnabled = C4BitfieldOperators<Enum>::value;

template<C4BitfieldOperatorsEnabled T>
constexpr T operator|(const T lhs, const T rhs) noexcept
{
	return static_cast<T>(std::to_underlying(lhs) | std::to_underlying(rhs));
}

template<C4BitfieldOperatorsEnabled T>
constexpr T operator&(const T lhs, const T rhs) noexcept
{
	return static_cast<T>(std::to_underlying(lhs) & std::to_underlying(rhs));
}

template<C4BitfieldOperatorsEnabled T>
constexpr T& operator|=(T& lhs, const T rhs) noexcept
{
	return lhs = (lhs | rhs);
}

template<C4BitfieldOperatorsEnabled T>
constexpr T& operator&=(T& lhs, const T rhs) noexcept
{
	return lhs = (lhs & rhs);
}

# Types

C4Script is dynamically typed. Every value has one of these types:

| Type | C4V_* | Example |
|---|---|---|
| `int` | `C4V_Int` | `42` |
| `bool` | `C4V_Bool` | `true` |
| `string` | `C4V_String` | `"hi"` |
| `object` | `C4V_Object` | `this` |
| `array` | `C4V_Array` | `[1,2,3]` |
| `proplist` | `C4V_PropList` | `{x=1}` |
| `id` | (definition id) | `Rock` |
| `any` | `C4V_Any` | unconstrained |

## Conversion

`int` and `bool` interoperate: `0` is `false`, anything else is `true`.
Strings convert to `0` in numeric context unless they parse as a number.

## Checking types

Use the `IsXxx` family or `TypeOf(v)` to inspect a value's type at runtime.

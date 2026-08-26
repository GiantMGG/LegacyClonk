# Syntax

C4Script uses C-like syntax with dynamic typing.

## Comments

```c
// Line comment.
/* Block comment. */
```

## Functions

```c
func MyFunction(int x) {
    return x + 1;
}
```

`private func` and `protected func` restrict visibility.

## Operators

Arithmetic: `+ - * / %`.
Comparison: `== != < <= > >=`.
Logical: `&& || !`.
Assignment: `= += -= *= /=`.

## Variables

```c
var a = 1;       // local
global b = 2;    // global to this script
```

## Strings

```c
var s = "Hello";
var t = "World";
Message("%s %s", this, s, t);
```

## Arrays

```c
var arr = [1, 2, 3];
arr[0] = 10;
```

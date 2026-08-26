# Control flow

C4Script supports the usual C control-flow constructs.

## if / else

```c
if (x > 0) {
    Log("positive");
} else {
    Log("non-positive");
}
```

## while

```c
var i = 0;
while (i < 10) {
    i += 1;
}
```

## for

```c
for (var i = 0; i < 10; i += 1) {
    Log("%d", i);
}
```

## return

```c
func Double(int x) {
    return x * 2;
}
```

## break / continue

`break` exits the enclosing loop. `continue` jumps to the next iteration.

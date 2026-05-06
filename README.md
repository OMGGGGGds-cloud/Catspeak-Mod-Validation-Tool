# Catspeak Mod Validation Tool v2.0

A zero-dependency Python CLI tool that validates `.meow` (Catspeak) mod files for GameMaker games. Detects syntax errors, GML→Catspeak conversion mistakes, and game-specific modding rule violations.

Works with **any GameMaker game** that uses the [Catspeak](https://github.com/katsaii/catspeak-lang) scripting language — not just STONKS-9800.

## Quick Start

```bash
# Validate a single mod
python mod_tool.py check my_mod.meow

# Validate all mods in a directory
python mod_tool.py check-all mods/

# Create a new mod from template
python mod_tool.py init "My Cool Mod" --advanced

# Scan and list all installed mods
python mod_tool.py scan mods/
```

Or just **double-click `ModTool.bat`** on Windows for an interactive menu.

## What It Detects

### Syntax Errors
- Unbalanced `{}`, `[]`, `()` with exact line numbers
- Missing `return` at file level
- Empty files

### GML → Catspeak Pitfalls
- `var` instead of `let`
- `function` instead of `fun`
- `//` used as comments (that's integer division in Catspeak!)
- `switch` instead of `match`
- `repeat` loops instead of `while`
- Ternary `? :` instead of `if/else` expressions

### Game-Specific Rules (customizable)
- Missing required mod struct fields (`name`, `description`)
- Invalid lifecycle callback names (with typo detection)
- `delay_action` without matching `mod_register_func`
- `while` loops inside draw callbacks (frame drop risk)

## Using With Other Games

### Generic Mode (Catspeak syntax only)

```bash
python mod_tool.py --generic check my_mod.meow
```

Skips all game-specific checks — only validates Catspeak syntax and GML pitfalls.

### Custom Game Config

**Step 1:** Generate a starter config:
```bash
python mod_tool.py --export-config "My Game Name"
```

**Step 2:** Edit the JSON — fill in your game's callbacks, API functions, etc.

**Step 3:** Use it:
```bash
python mod_tool.py --config my_game.json check my_mod.meow
```

## Requirements

- Python 3.7+
- No external dependencies

## License

MIT

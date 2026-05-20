"""Smart calculator tool for NovaPilot.

Provides safe mathematical expression evaluation, unit conversions,
and support for common mathematical functions.
Uses a restricted evaluation environment to prevent code injection.
"""

import math
import re


# Safe math functions and constants for evaluation
SAFE_MATH_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": pow,
    "divmod": divmod,
    "int": int,
    "float": float,
    "len": len,
    # Math module functions
    "sqrt": math.sqrt,
    "cbrt": lambda x: x ** (1/3),
    "floor": math.floor,
    "ceil": math.ceil,
    "trunc": math.trunc,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "degrees": math.degrees,
    "radians": math.radians,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "hypot": math.hypot,
    "isfinite": math.isfinite,
    "isinf": math.isinf,
    "isnan": math.isnan,
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
    "nan": math.nan,
}

# Unit conversion tables
UNIT_CONVERSIONS = {
    # Length
    "length": {
        "m": 1.0,
        "km": 1000.0,
        "cm": 0.01,
        "mm": 0.001,
        "mi": 1609.344,
        "yd": 0.9144,
        "ft": 0.3048,
        "in": 0.0254,
        "nm": 1852.0,
    },
    # Weight/Mass
    "weight": {
        "kg": 1.0,
        "g": 0.001,
        "mg": 0.000001,
        "lb": 0.453592,
        "oz": 0.0283495,
        "t": 1000.0,
    },
    # Temperature (handled separately)
    "temperature": {
        "c": "celsius",
        "f": "fahrenheit",
        "k": "kelvin",
    },
    # Data
    "data": {
        "b": 1,
        "kb": 1024,
        "mb": 1024 ** 2,
        "gb": 1024 ** 3,
        "tb": 1024 ** 4,
        "pb": 1024 ** 5,
    },
    # Time
    "time": {
        "s": 1,
        "ms": 0.001,
        "us": 0.000001,
        "min": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
        "y": 31536000,
    },
}


class Calculator:
    """Smart calculator with safe expression evaluation.

    Evaluates mathematical expressions in a restricted environment,
    preventing code injection while supporting a wide range of
    mathematical operations and unit conversions.
    """

    # Trigger patterns for automatic tool activation
    trigger_patterns = [
        "calculate", "compute", "math", "convert",
        "how much is", "what is", "= ",
    ]

    # Pattern to detect unit conversion requests
    UNIT_PATTERN = re.compile(
        r'(\d+\.?\d*)\s*(kg|g|mg|lb|oz|t|km|m|cm|mm|mi|yd|ft|in|nm|'
        r'kb|mb|gb|tb|pb|b|s|ms|us|min|h|d|w|y|c|f|k)'
        r'\s*(?:to|in|=>|=)\s*'
        r'(kg|g|mg|lb|oz|t|km|m|cm|mm|mi|yd|ft|in|nm|'
        r'kb|mb|gb|tb|pb|b|s|ms|us|min|h|d|w|y|c|f|k)',
        re.IGNORECASE,
    )

    def __init__(self):
        """Initialize Calculator."""
        self._history = []

    def evaluate(self, expression):
        """Safely evaluate a mathematical expression.

        The expression is evaluated in a restricted namespace containing
        only safe math functions. No builtins or imports are available.

        Args:
            expression: Mathematical expression string.

        Returns:
            Evaluation result (numeric type).

        Raises:
            ValueError: If the expression is empty or contains unsafe code.
            SyntaxError: If the expression has invalid syntax.
            ZeroDivisionError: If division by zero occurs.
        """
        if not expression or not expression.strip():
            raise ValueError("Empty expression.")

        # Preprocess expression
        expr = self._preprocess(expression)

        # Security check: only allow safe characters
        if not self._is_safe(expr):
            raise ValueError(
                "Expression contains potentially unsafe characters or patterns."
            )

        # Build restricted namespace
        safe_namespace = dict(SAFE_MATH_FUNCTIONS)

        try:
            result = eval(expr, {"__builtins__": {}}, safe_namespace)
        except ZeroDivisionError:
            raise ZeroDivisionError("Division by zero.")
        except SyntaxError as e:
            raise SyntaxError(f"Invalid expression syntax: {e}")
        except NameError as e:
            raise ValueError(f"Unknown function or variable: {e}")
        except TypeError as e:
            raise ValueError(f"Type error in expression: {e}")

        # Round to reasonable precision
        if isinstance(result, float):
            result = round(result, 10)
            # Remove trailing zeros
            if result == int(result):
                result = int(result)

        self._history.append({
            "expression": expression,
            "result": result,
        })

        return result

    def _preprocess(self, expression):
        """Preprocess expression for evaluation.

        Handles common notation variations like '^' for power,
        implicit multiplication, etc.

        Args:
            expression: Raw expression string.

        Returns:
            Preprocessed expression string.
        """
        expr = expression.strip()

        # Replace ^ with ** for exponentiation
        expr = expr.replace("^", "**")

        # Handle percentage
        expr = re.sub(r'(\d+\.?\d*)%', r'(\1/100)', expr)

        # Handle implicit multiplication: 2(3) -> 2*(3), (2)(3) -> (2)*(3)
        expr = re.sub(r'(\d)\(', r'\1*(', expr)
        expr = re.sub(r'\)(\d)', r')*\1', expr)
        expr = re.sub(r'\)\(', r')*(', expr)

        # Handle math constants
        expr = re.sub(r'\bpi\b', 'math_pi', expr)
        expr = re.sub(r'\be\b(?!xp)', 'math_e', expr)
        expr = expr.replace("math_pi", "pi")
        expr = expr.replace("math_e", "e")

        return expr

    def _is_safe(self, expression):
        """Check if an expression contains only safe characters.

        Blocks access to Python builtins, imports, attribute access
        on non-math objects, and other potentially dangerous patterns.

        Args:
            expression: Preprocessed expression string.

        Returns:
            True if the expression appears safe, False otherwise.
        """
        # Remove whitespace and safe characters, check if anything remains
        # Allowed: digits, operators, parentheses, dots, commas, underscores, letters
        dangerous_patterns = [
            r'import\b', r'__\w+__', r'exec\b', r'eval\b',
            r'compile\b', r'open\b', r'getattr\b', r'setattr\b',
            r'delattr\b', r'globals\b', r'locals\b', r'input\b',
            r'print\b', r'break', r'continue', r'raise\b',
            r'class\b', r'def\b', r'lambda\b', r'yield\b',
            r'assert\b', r'with\b', r'for\b', r'while\b',
            r'if\b', r'else\b', r'try\b', r'except\b',
            r'finally\b', r'return\b', r'pass\b',
            r'\[', r'\{', r'\}', r'@', r';', r':',
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, expression):
                return False

        # Check for attribute access (except on known safe objects)
        # Only flag dots that are NOT part of decimal numbers
        # A decimal dot is surrounded by digits: digit.digit
        if "." in expression:
            # Remove decimal numbers before checking attribute access
            cleaned = re.sub(r'\b\d+\.\d+\b', '0', expression)
            parts = cleaned.split(".")
            for i, part in enumerate(parts):
                if i > 0 and part:
                    # This is an attribute access
                    # Allow if it's a function call or a number
                    if not re.match(r'^\w+\s*\(', part) and not re.match(r'^\d+$', part):
                        # Could be unsafe
                        if part.strip() not in SAFE_MATH_FUNCTIONS:
                            return False

        return True

    def convert_unit(self, value, from_unit, to_unit):
        """Convert a value between units.

        Args:
            value: Numeric value to convert.
            from_unit: Source unit string.
            to_unit: Target unit string.

        Returns:
            Converted numeric value.

        Raises:
            ValueError: If units are not compatible or unknown.
        """
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()

        # Temperature conversion (special case)
        if from_unit in ("c", "f", "k") and to_unit in ("c", "f", "k"):
            return self._convert_temperature(value, from_unit, to_unit)

        # Find the conversion category
        for category, units in UNIT_CONVERSIONS.items():
            if category == "temperature":
                continue
            if from_unit in units and to_unit in units:
                # Convert to base unit, then to target
                base_value = value * units[from_unit]
                result = base_value / units[to_unit]
                return round(result, 6)

        raise ValueError(
            f"Cannot convert from '{from_unit}' to '{to_unit}'. "
            f"Unknown or incompatible units."
        )

    def _convert_temperature(self, value, from_unit, to_unit):
        """Convert temperature between Celsius, Fahrenheit, and Kelvin.

        Args:
            value: Temperature value.
            from_unit: Source unit ('c', 'f', 'k').
            to_unit: Target unit ('c', 'f', 'k').

        Returns:
            Converted temperature value.
        """
        if from_unit == to_unit:
            return value

        # Convert to Celsius first
        if from_unit == "c":
            celsius = value
        elif from_unit == "f":
            celsius = (value - 32) * 5 / 9
        elif from_unit == "k":
            celsius = value - 273.15
        else:
            raise ValueError(f"Unknown temperature unit: {from_unit}")

        # Convert from Celsius to target
        if to_unit == "c":
            return round(celsius, 2)
        elif to_unit == "f":
            return round(celsius * 9 / 5 + 32, 2)
        elif to_unit == "k":
            return round(celsius + 273.15, 2)
        else:
            raise ValueError(f"Unknown temperature unit: {to_unit}")

    def parse_and_evaluate(self, text):
        """Parse natural language input and evaluate or convert.

        Attempts to detect whether the input is a unit conversion
        or mathematical expression, and handles accordingly.

        Args:
            text: Natural language input string.

        Returns:
            Result string with the answer.
        """
        text = text.strip()

        # Try unit conversion
        unit_match = self.UNIT_PATTERN.search(text)
        if unit_match:
            value = float(unit_match.group(1))
            from_unit = unit_match.group(2)
            to_unit = unit_match.group(3)
            try:
                result = self.convert_unit(value, from_unit, to_unit)
                return f"{value} {from_unit} = {result} {to_unit}"
            except ValueError as e:
                return str(e)

        # Try mathematical evaluation
        # Extract the expression part (remove common prefixes)
        expr = re.sub(
            r'^(calculate|compute|eval|what is|how much is|solve)\s*',
            '', text, flags=re.IGNORECASE
        ).strip()

        # Remove trailing question marks
        expr = expr.rstrip("?").strip()

        if not expr:
            return "No expression to evaluate."

        try:
            result = self.evaluate(expr)
            return f"{expr} = {result}"
        except (ValueError, SyntaxError, ZeroDivisionError) as e:
            return f"Error: {e}"

    def get_history(self, limit=10):
        """Get calculation history.

        Args:
            limit: Maximum number of history entries.

        Returns:
            List of recent calculation dicts.
        """
        return self._history[-limit:]

    def clear_history(self):
        """Clear calculation history."""
        self._history.clear()

    def execute(self, args):
        """Execute calculation (tool interface).

        Args:
            args: Expression string or dict with 'expression' key.

        Returns:
            Result string.
        """
        if isinstance(args, dict):
            if "action" in args and args["action"] == "convert":
                return str(self.convert_unit(
                    args["value"], args["from"], args["to"]
                ))
            expression = args.get("expression", args.get("query", ""))
        else:
            expression = str(args)

        return self.parse_and_evaluate(expression)

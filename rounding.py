
"""
rounding.py

This module demonstrates rounding by significant digits/bits using:
1. Chopping / truncation (toward zero)
2. Round up (toward +infinity)
3. Round down (toward -infinity)
4. Round to nearest, ties to even

Supported input types:
- Decimal numbers
- Binary numbers

Design goals:
- Reusable functions for later GUI integration
- Exact decimal handling using Python's Decimal class
- String-based binary rounding to avoid floating-point errors
- Clear step-by-step explanations
- Input validation
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_DOWN,
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    localcontext,
)
import re
from typing import Dict


DECIMAL32_MAX_SIGNIFICANT_DIGITS = 7


@dataclass
class RoundingResult:
    input_type: str
    original: str
    target_digits: int
    chopping: str
    round_up: str
    round_down: str
    ties_to_even: str
    explanation: Dict[str, str]

# CHECK INPUT

def validate_target_digits(target_digits: int) -> int:
    """Check if the target digits/bits are valid."""
    if not isinstance(target_digits, int):
        raise ValueError("Target digits must be a whole number.")
    if target_digits < 1:
        raise ValueError("Target digits must be at least 1.")
    return target_digits

# DECIMAL ROUNDING

_DECIMAL_PATTERN = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
)


def validate_decimal_string(value: str) -> str:
    """Check the decimal input and return a clean version."""
    if value is None:
        raise ValueError("Decimal input cannot be empty.")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Decimal input cannot be empty.")

    if not _DECIMAL_PATTERN.fullmatch(cleaned):
        raise ValueError(
            "Invalid decimal input. Examples: 12.345, -0.7783, 1.23e5"
        )

    try:
        number = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal input.") from exc

    if not number.is_finite():
        raise ValueError("This rounding module accepts finite numbers only.")

    return cleaned


def count_decimal_significant_digits(value: str) -> int:

    cleaned = validate_decimal_string(value)
    unsigned = cleaned.lstrip("+-")

    if "e" in unsigned.lower():
        coefficient = re.split(r"[eE]", unsigned)[0]
    else:
        coefficient = unsigned

    if "." in coefficient:
        digits = coefficient.replace(".", "")
        stripped = digits.lstrip("0")
        return len(stripped) if stripped else 1

    stripped_leading = coefficient.lstrip("0")
    if not stripped_leading:
        return 1

    stripped_trailing = stripped_leading.rstrip("0")
    return len(stripped_trailing) if stripped_trailing else 1


def _decimal_place(number: Decimal, significant_digits: int) -> Decimal:
 
    if number.is_zero():
        return Decimal(1).scaleb(-(significant_digits - 1))

    adjusted_exponent = number.copy_abs().adjusted()
    # Find the place to round to
    place_exponent = adjusted_exponent - significant_digits + 1
    return Decimal(1).scaleb(place_exponent)


def _format_decimal_significant(
    rounded: Decimal,
    significant_digits: int,
) -> str:

    if rounded.is_zero():
        if significant_digits == 1:
            return "0"
        return "0." + ("0" * (significant_digits - 1))

    adjusted = rounded.copy_abs().adjusted()

    if adjusted >= significant_digits or adjusted <= -5:
        return f"{rounded:.{significant_digits - 1}E}"

    decimal_places = max(significant_digits - adjusted - 1, 0)
    return f"{rounded:.{decimal_places}f}"


def _round_decimal_mode(
    number: Decimal,
    significant_digits: int,
    rounding_mode: str,
) -> Decimal:
    place = _decimal_place(number, significant_digits)

    with localcontext() as ctx:
        ctx.prec = max(
            50,
            len(number.as_tuple().digits) + abs(number.as_tuple().exponent) + 20,
        )
        return number.quantize(place, rounding=rounding_mode)


def round_decimal_significant(
    value: str,
    target_digits: int,
) -> RoundingResult:
    cleaned = validate_decimal_string(value)
    target_digits = validate_target_digits(target_digits)
    number = Decimal(cleaned)

    chopped = _round_decimal_mode(number, target_digits, ROUND_DOWN)
    rounded_up = _round_decimal_mode(number, target_digits, ROUND_CEILING)
    rounded_down = _round_decimal_mode(number, target_digits, ROUND_FLOOR)
    nearest_even = _round_decimal_mode(number, target_digits, ROUND_HALF_EVEN)

    original_count = count_decimal_significant_digits(cleaned)

    explanations = {
        "chopping": (
            "Round toward zero. Discard digits after the target position "
            "without increasing the retained part."
        ),
        "round_up": (
            "Round toward positive infinity. If discarded digits are nonzero, "
            "a positive value moves upward while a negative value moves closer to zero."
        ),
        "round_down": (
            "Round toward negative infinity. If discarded digits are nonzero, "
            "a positive value moves toward zero while a negative value becomes more negative."
        ),
        "ties_to_even": (
            "Round to the nearest value. If exactly halfway, choose the result "
            "whose last retained digit is even."
        ),
        "input": (
            f"The input has {original_count} significant digit(s)"
            f"The requested precision is {target_digits} significant digit(s)."
        ),
    }

    return RoundingResult(
        input_type="decimal",
        original=cleaned,
        target_digits=target_digits,
        chopping=_format_decimal_significant(chopped, target_digits),
        round_up=_format_decimal_significant(rounded_up, target_digits),
        round_down=_format_decimal_significant(rounded_down, target_digits),
        ties_to_even=_format_decimal_significant(nearest_even, target_digits),
        explanation=explanations,
    )

# BINARY ROUNDING

_BINARY_PATTERN = re.compile(
    r"^[+-]?(?:[01]+(?:\.[01]*)?|\.[01]+)(?:[pP][+-]?\d+)?$"
)


@dataclass
class ParsedBinary:
    sign: int
    coefficient_bits: str
    point_index: int
    exponent2: int
    original: str


def validate_binary_string(value: str) -> str:
    """
    Validate binary input.

    Accepted examples:
    101.011
    -0.100101
    1.001p5   (binary scientific form: 1.001 x 2^5)
    """
    if value is None:
        raise ValueError("Binary input cannot be empty.")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Binary input cannot be empty.")

    if not _BINARY_PATTERN.fullmatch(cleaned):
        raise ValueError(
            "Invalid binary input. Use only 0, 1, one radix point, "
            "and optional p exponent, e.g. 101.011 or 1.001p5."
        )

    return cleaned


def parse_binary(value: str) -> ParsedBinary:
    """Read a normal or p-exponent binary string."""
    cleaned = validate_binary_string(value)
    sign = -1 if cleaned.startswith("-") else 1
    unsigned = cleaned.lstrip("+-")

    if "p" in unsigned.lower():
        coefficient, exponent_text = re.split(r"[pP]", unsigned)
        exponent2 = int(exponent_text)
    else:
        coefficient = unsigned
        exponent2 = 0

    if "." in coefficient:
        whole, fraction = coefficient.split(".", 1)
    else:
        whole, fraction = coefficient, ""

    coefficient_bits = whole + fraction
    point_index = len(whole) + exponent2

    return ParsedBinary(
        sign=sign,
        coefficient_bits=coefficient_bits,
        point_index=point_index,
        exponent2=exponent2,
        original=cleaned,
    )


def count_binary_significant_bits(value: str) -> int:
    """
    Count significant bits:
    - Leading zeroes are not significant.
    - Zeroes between significant 1s are significant.
    - Trailing zeroes after a radix point are significant.
    - Trailing zeroes without a radix point are treated as ambiguous.
    """
    parsed = parse_binary(value)
    unsigned = parsed.original.lstrip("+-")
    coefficient = re.split(r"[pP]", unsigned)[0]

    if "." in coefficient:
        digits = coefficient.replace(".", "")
        stripped = digits.lstrip("0")
        return len(stripped) if stripped else 1

    stripped_leading = coefficient.lstrip("0")
    if not stripped_leading:
        return 1

    stripped_trailing = stripped_leading.rstrip("0")
    return len(stripped_trailing) if stripped_trailing else 1


def _normalize_binary(parsed: ParsedBinary) -> tuple[str, int]:
    """
    Normalize binary input to a bit string and scientific exponent.

    Returns:
        significant_bits, exponent

    Example:
        101.011 -> ("101011", 2), meaning 1.01011 x 2^2
        0.00101 -> ("101", -3), meaning 1.01 x 2^-3
    """
    bits = parsed.coefficient_bits
    first_one = bits.find("1")

    if first_one == -1:
        return "0", 0

    exponent = parsed.point_index - first_one - 1
    significant_bits = bits[first_one:]
    return significant_bits, exponent


def _increment_binary(bits: str) -> tuple[str, bool]:
    """
    Add 1 to a binary significand string.

    Returns:
        incremented bits, overflowed

    Example:
        101 -> 110, False
        111 -> 1000, True
    """
    result = list(bits)
    carry = 1

    for index in range(len(result) - 1, -1, -1):
        if carry == 0:
            break
        if result[index] == "0":
            result[index] = "1"
            carry = 0
        else:
            result[index] = "0"

    if carry:
        return "1" + "".join(result), True

    return "".join(result), False


def _binary_round_decision(
    retained: str,
    discarded: str,
    sign: int,
    mode: str,
) -> bool:
    """Return True if we need to add 1."""
    discarded_nonzero = "1" in discarded

    if not discarded_nonzero:
        return False

    if mode == "chopping":
        return False

    if mode == "round_up":
        return sign > 0

    if mode == "round_down":
        return sign < 0

    if mode == "ties_to_even":
        first = discarded[0]
        rest = discarded[1:]

        if first == "0":
            return False

        if "1" in rest:
            return True

        # Halfway case: discarded bits are 1000...
        return retained[-1] == "1"

    raise ValueError(f"Unknown rounding mode: {mode}")


def _format_binary_scientific(
    sign: int,
    retained: str,
    exponent: int,
    target_bits: int,
) -> str:
    """Format the binary result in base-2 form."""
    prefix = "-" if sign < 0 else ""

    if retained == "0" or set(retained) == {"0"}:
        if target_bits == 1:
            return "0"
        return "0." + ("0" * (target_bits - 1))

    retained = retained.ljust(target_bits, "0")

    if target_bits == 1:
        coefficient = retained[0]
    else:
        coefficient = retained[0] + "." + retained[1:]

    return f"{prefix}{coefficient} x 2^{exponent}"


def _round_binary_mode(
    parsed: ParsedBinary,
    target_bits: int,
    mode: str,
) -> str:
    """Round the binary number to the wanted bits."""
    significant_bits, exponent = _normalize_binary(parsed)

    if significant_bits == "0":
        return _format_binary_scientific(
            parsed.sign, "0", 0, target_bits
        )

    if len(significant_bits) <= target_bits:
        retained = significant_bits.ljust(target_bits, "0")
        return _format_binary_scientific(
            parsed.sign, retained, exponent, target_bits
        )

    retained = significant_bits[:target_bits]
    discarded = significant_bits[target_bits:]

    increment = _binary_round_decision(
        retained=retained,
        discarded=discarded,
        sign=parsed.sign,
        mode=mode,
    )

    if increment:
        retained, overflowed = _increment_binary(retained)
        if overflowed:
            exponent += 1
            retained = retained[:target_bits]

    return _format_binary_scientific(
        parsed.sign, retained, exponent, target_bits
    )


def round_binary_significant(
    value: str,
    target_bits: int,
) -> RoundingResult:
    """Run all four rounding methods for binary."""
    parsed = parse_binary(value)
    target_bits = validate_target_digits(target_bits)
    original_count = count_binary_significant_bits(value)

    normalized_bits, normalized_exp = _normalize_binary(parsed)

    if normalized_bits == "0":
        discarded_description = "The input is zero, so no nonzero bits are discarded."
    elif len(normalized_bits) <= target_bits:
        discarded_description = (
            "The input already fits the requested precision, so no nonzero bits are discarded."
        )
    else:
        retained = normalized_bits[:target_bits]
        discarded = normalized_bits[target_bits:]
        midpoint = (
            discarded.startswith("1")
            and set(discarded[1:]) <= {"0"}
        )
        discarded_description = (
            f"\nNormalized form: 1.{normalized_bits[1:]} x 2^{normalized_exp}. "
            f"\nRetained bits: {retained}. \nDiscarded bits: {discarded}. "
            + (
                "\nThe discarded portion is exactly halfway."
                if midpoint
                else "\nThe discarded portion is not an exact halfway case."
            )
        )

    explanations = {
        "chopping": (
            "Round toward zero by discarding all bits after the target position."
        ),
        "round_up": (
            "Round toward positive infinity. Increment only when discarded bits "
            "are nonzero and the number is positive."
        ),
        "round_down": (
            "Round toward negative infinity. Increment the magnitude only when "
            "discarded bits are nonzero and the number is negative."
        ),
        "ties_to_even": (
            "Round to the nearest binary value. An exact halfway case has discarded "
            "bits 1000...; choose the result with least significant retained bit 0."
        ),
        "input": (
            f"The input has {original_count} significant bit(s). "
            f"The requested precision is {target_bits} significant bit(s). "
            f"{discarded_description}"
        ),
    }

    return RoundingResult(
        input_type="binary",
        original=parsed.original,
        target_digits=target_bits,
        chopping=_round_binary_mode(parsed, target_bits, "chopping"),
        round_up=_round_binary_mode(parsed, target_bits, "round_up"),
        round_down=_round_binary_mode(parsed, target_bits, "round_down"),
        ties_to_even=_round_binary_mode(parsed, target_bits, "ties_to_even"),
        explanation=explanations,
    )

# PUBLIC WRAPPER AND DISPLAY

def calculate_all_rounding_methods(
    value: str,
    target_digits: int,
    input_type: str,
) -> RoundingResult:
    """
    Reusable wrapper for terminal or future GUI use.

    input_type:
        "decimal" or "binary"
    """
    normalized_type = input_type.strip().lower()

    if normalized_type == "decimal":
        return round_decimal_significant(value, target_digits)

    if normalized_type == "binary":
        return round_binary_significant(value, target_digits)

    raise ValueError("Input type must be 'decimal' or 'binary'.")


def print_result(result: RoundingResult) -> None:
    """Print the results."""
    unit = "digits" if result.input_type == "decimal" else "bits"

    print("\n" + "=" * 68)
    print("IEEE-754 ROUNDING DEMONSTRATION")
    print("=" * 68)
    print(f"Input type      : {result.input_type.capitalize()}")
    print(f"Original input  : {result.original}")
    print(f"Target precision: {result.target_digits} significant {unit}")
    print("-" * 68)
    print(result.explanation["input"])
    print("-" * 68)

    print(f"1. Chopping / toward zero")
    print(f"   Result      : {result.chopping}")
    print(f"   Explanation : {result.explanation['chopping']}\n")

    print(f"2. Round up / toward +infinity")
    print(f"   Result      : {result.round_up}")
    print(f"   Explanation : {result.explanation['round_up']}\n")

    print(f"3. Round down / toward -infinity")
    print(f"   Result      : {result.round_down}")
    print(f"   Explanation : {result.explanation['round_down']}\n")

    print(f"4. Round to nearest, ties to even")
    print(f"   Result      : {result.ties_to_even}")
    print(f"   Explanation : {result.explanation['ties_to_even']}")
    print("=" * 68)


def run_terminal() -> None:
    """Run the terminal program."""
    print("=" * 68)
    print("MACHINE 4 - DECIMAL32 ROUNDING METHODS")
    print("=" * 68)
    print("This program rounds by significant digits/bits.")
    print("Type 'exit' at any main prompt to quit.\n")

    while True:
        try:
            print("Choose input type:")
            print("1 - Decimal")
            print("2 - Binary")
            choice = input("Selection: ").strip()

            if choice.lower() == "exit":
                break

            if choice == "1":
                input_type = "decimal"
                value = input(
                    "Enter a decimal number (e.g. -0.7783): "
                ).strip()
            elif choice == "2":
                input_type = "binary"
                value = input(
                    "Enter a binary number (e.g. 0.100101110 or 1.001p5): "
                ).strip()
            else:
                print("\nError: Please choose 1 or 2.\n")
                continue

            if value.lower() == "exit":
                break

            digits_text = input(
                "Enter target significant digits/bits: "
            ).strip()

            if digits_text.lower() == "exit":
                break

            if not digits_text.isdigit():
                raise ValueError("Target digits must be a positive whole number.")

            target_digits = int(digits_text)
            result = calculate_all_rounding_methods(
                value=value,
                target_digits=target_digits,
                input_type=input_type,
            )
            print_result(result)

            again = input("\nRound another number? (y/n): ").strip().lower()
            if again not in {"y", "yes"}:
                break
            print()

        except ValueError as error:
            print(f"\nError: {error}\n")
        except KeyboardInterrupt:
            print("\n\nProgram ended.")
            break

    print("\nThank you for using the Machine 4 rounding module.")


if __name__ == "__main__":
    run_terminal()

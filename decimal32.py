import re

_DECIMAL_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")

def encode_dpd(d1, d2, d3):
    """
    Converts 3 decimal digits into a 10-bit Densely Packed Decimal (DPD).
    """
    b1, b2, b3 = f"{d1:04b}", f"{d2:04b}", f"{d3:04b}"
    a, b, c, d = b1[0], b1[1], b1[2], b1[3]
    e, f, g, h = b2[0], b2[1], b2[2], b2[3]
    i, j, k, m = b3[0], b3[1], b3[2], b3[3]
    
    aei = a + e + i
    
    if aei == "000": return b+c+d + f+g+h + "0" + j+k+m
    elif aei == "001": return b+c+d + f+g+h + "100" + m
    elif aei == "010": return b+c+d + j+k+h + "101" + m
    elif aei == "011": return b+c+d + "10" + h + "111" + m
    elif aei == "100": return j+k+d + f+g+h + "110" + m
    elif aei == "101": return f+g+d + "01" + h + "111" + m
    elif aei == "110": return j+k+d + "00" + h + "111" + m
    elif aei == "111": return "00" + d + "11" + h + "111" + m

def decimal32_encode(base_str, exp_str="0"):
    print("\n--- BEGIN PARSING TRACE ---")
    
    base_lower = base_str.lower()
    if base_lower in ["infinity", "+infinity", "inf", "+inf"]:
        print("Trace: Positive Infinity detected.")
        return {"sign": "0", "comb": "11110", "exp_cont": "000000", "coeff_cont": "0000000000 0000000000"}
    if base_lower in ["-infinity", "-inf"]:
        print("Trace: Negative Infinity detected.")
        return {"sign": "1", "comb": "11110", "exp_cont": "000000", "coeff_cont": "0000000000 0000000000"}
    if base_lower == "nan":
        print("Trace: NaN (Not a Number) detected.")
        return {"sign": "0", "comb": "11111", "exp_cont": "000000", "coeff_cont": "0000000000 0000000000"}

    if _DECIMAL_PATTERN.fullmatch(base_str) is None:
        raise ValueError(
            "Invalid decimal number. Use digits, an optional sign, and a single decimal point."
        )

    is_negative = False
    if base_str.startswith("-"):
        is_negative = True
        base_str = base_str[1:]
    elif base_str.startswith("+"):
        base_str = base_str[1:]
        
    sign_bit = "1" if is_negative else "0"
    print(f"Step 1: Check sign. Input is {'negative' if is_negative else 'positive'}, sign bit = {sign_bit}")
    
    if "." in base_str:
        left, right = base_str.split(".")
        whole_num = int(left + right)
        exp_shift = len(right)
        print(f"Step 2: Not a fully whole number. Shift radix right by {exp_shift}. Adjusted exponent: {exp_str} - {exp_shift} = {int(exp_str) - exp_shift}")
    else:
        whole_num = int(base_str)
        exp_shift = 0
        print(f"Step 2: Already a whole number. No radix shift needed.")
        
    final_exp = int(exp_str) - exp_shift
    digits_str = str(whole_num)

    # Cohort normalization to enforce E_max bounds
    if final_exp > 90:
        shifts = 0
        while final_exp > 90 and len(digits_str) < 7:
            whole_num *= 10
            final_exp -= 1
            digits_str = str(whole_num)
            shifts += 1
        if shifts > 0:
            print(f"Step 2b: Exponent exceeds max normal (90). Shift radix right {shifts} times -> {digits_str} x 10^{final_exp}")

    # Cohort normalization to salvage E_min underflows (stripping trailing zeros)
    if final_exp < -101:
        shifts = 0
        # Only shift if it divides perfectly by 10 (trailing zero)
        while final_exp < -101 and whole_num % 10 == 0 and whole_num != 0:
            whole_num //= 10
            final_exp += 1
            digits_str = str(whole_num)
            shifts += 1
        if shifts > 0:
            print(f"Step 2c: Exponent is below absolute min (-101). Shift radix left {shifts} times -> {digits_str} x 10^{final_exp}")
    
    if len(digits_str) > 7:
        raise ValueError("Error: Input exceeds the 7 significant digits limit.")
        
    padded_digits = digits_str.zfill(7)
    print(f"Step 3: Check if normalized to 7 whole digits. Pad leading 0's to the left: {padded_digits} x 10^{final_exp}")
    
    # Check bounds against absolute stored limits
    if final_exp > 90: 
        print("Trace: Exponent still exceeds max limit (90) after max radix shifts. Overflow to Infinity.")
        return {"sign": sign_bit, "comb": "11110", "exp_cont": "000000", "coeff_cont": "0000000000 0000000000"}
        
    if final_exp < -101:
        raise ValueError(f"Error: Adjusted exponent ({final_exp}) is below Decimal32 minimum bound (-101).")
    
    e_biased = final_exp + 101
    print(f"Step 4: Now normalized, get exponent representation: e = {final_exp} + 101 (bias) = {e_biased}")
    
    exp_bin = f"{e_biased:08b}"
    print(f"Step 5: Turn exponent representation ({e_biased}) into 8-bit binary = {exp_bin}")
    
    exp_2bits = exp_bin[0:2]
    print(f"Step 6: The 2 leftmost bits of the exponent ({exp_2bits}) will be used for combination field.")
    
    msd = int(padded_digits[0])
    msd_bin = f"{msd:04b}"
    print(f"Step 7: Identify most significant digit in {padded_digits} which is {msd}.")
    print(f"Step 8: Turn MSD into 4-bit binary = {msd_bin}.")
    
    if msd >= 0 and msd <= 7:
        comb_field = exp_2bits + msd_bin[-3:]
        print(f"Step 9: MSD is 0-7. Combination field (abcde): ab ({exp_2bits}) + cde ({msd_bin[-3:]}) = {comb_field}")
    else:
        comb_field = "11" + exp_2bits + msd_bin[-1:]
        print(f"Step 9: MSD is 8-9. Combination field (11cde): 11 + cd ({exp_2bits}) + e ({msd_bin[-1:]}) = {comb_field}")
        
    exp_cont = exp_bin[2:8]
    print(f"Step 10: Exponent continuation (6 remaining bits from exponent) = {exp_cont}")
    
    group1 = padded_digits[1:4]
    group2 = padded_digits[4:7]
    
    dpd1 = encode_dpd(int(group1[0]), int(group1[1]), int(group1[2]))
    dpd2 = encode_dpd(int(group2[0]), int(group2[1]), int(group2[2]))
    
    print(f"Step 11: Coefficient continuation (DPD of {group1} and {group2}):")
    print(f"         {group1} -> {dpd1}")
    print(f"         {group2} -> {dpd2}")
    print("--- END PARSING TRACE ---\n")
    
    coeff_cont = f"{dpd1} {dpd2}"
    
    return {
        "sign": sign_bit,
        "comb": comb_field,
        "exp_cont": exp_cont,
        "coeff_cont": coeff_cont
    }

def print_outputs(base_val, exp_val="0"):
    print(f"\n========================================")
    print(f"INPUT: {base_val} x 10^{exp_val}")
    print(f"========================================")
    try:
        fields = decimal32_encode(base_val, exp_val)
        
        print(f"Sign bit: {fields['sign']}")
        print(f"Combination field: {fields['comb']}")
        print(f"Exponent continuation field: {fields['exp_cont']}")
        print(f"Coefficient continuation field: {fields['coeff_cont']}")
        
        binary_spaced = f"{fields['sign']} {fields['comb']} {fields['exp_cont']} {fields['coeff_cont']}"
        print(f"\nBinary : {binary_spaced}")
        
        bin_solid = binary_spaced.replace(" ", "")
        hex_val = f"{int(bin_solid, 2):08X}"
        print(f"Hex    : 0x{hex_val}\n")
        
    except ValueError as e:
        print(f"\n{e}\n")

if __name__ == "__main__":
    print("========================================")
    print("      Decimal32 IEEE 754 Encoder        ")
    print("========================================")
    print("Type 'exit' in the decimal prompt to quit.\n")
    
    while True:
        base_input = input("Enter the decimal base (e.g. 122.5): ").strip()
        if base_input.lower() == 'exit':
            break
            
        if base_input.lower() in ["infinity", "+infinity", "-infinity", "inf", "+inf", "-inf", "nan"]:
            print_outputs(base_input, "0")
            continue
            
        exp_input = input("Enter the base-10 exponent (e.g. 0): ").strip()
        
        if exp_input == "":
            exp_input = "0"
            
        print_outputs(base_input, exp_input)

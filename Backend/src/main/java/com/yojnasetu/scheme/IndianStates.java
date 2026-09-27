package com.yojnasetu.scheme;

import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Pattern;

/** The 28 states and 8 union territories, used to validate a user's state. */
public final class IndianStates {

	public static final List<String> ALL = List.of("Andaman and Nicobar Islands", "Andhra Pradesh",
			"Arunachal Pradesh", "Assam", "Bihar", "Chandigarh", "Chhattisgarh",
			"Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
			"Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh",
			"Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab",
			"Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
			"West Bengal");

	private IndianStates() {
	}

	/** Canonical name for user input, tolerant of case, "&" versus "and", and a leading "The". */
	public static Optional<String> canonical(String input) {
		String key = normalize(input);
		return ALL.stream().filter(s -> normalize(s).equals(key)).findFirst();
	}

	/** Whether two state labels (for example a user's state and a scheme's state) name the same place. */
	public static boolean same(String a, String b) {
		return a != null && b != null && normalize(a).equals(normalize(b));
	}

	/** Database pattern matching the stored spellings of a canonical state name. */
	static Pattern labelPattern(String canonical) {
		String words = String.join("\\s+", Arrays.stream(canonical.split("\\s+"))
			.map(w -> w.equalsIgnoreCase("and") ? "(and|&)" : Pattern.quote(w))
			.toList());
		return Pattern.compile("^(the\\s+)?" + words + "$", Pattern.CASE_INSENSITIVE);
	}

	private static String normalize(String value) {
		return value == null ? ""
				: value.toLowerCase(Locale.ROOT).replace("&", " and ").replaceAll("^\\s*the\\s+", "")
					.replaceAll("[^a-z]+", " ").trim();
	}

}

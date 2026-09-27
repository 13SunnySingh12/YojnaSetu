package com.yojnasetu.scheme;

/**
 * Optional list filters. {@code state} must already be canonical (see {@link IndianStates}); {@code need} a
 * key of {@link Needs}.
 */
public record SchemeFilter(String q, String category, String state, String gender, Integer age,
		String beneficiaryType, String level, String need) {

	public static SchemeFilter none() {
		return new SchemeFilter(null, null, null, null, null, null, null, null);
	}

}

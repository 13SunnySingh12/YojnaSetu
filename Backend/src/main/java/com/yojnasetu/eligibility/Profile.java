package com.yojnasetu.eligibility;

/** The user's answers. Any field may be null, meaning the user did not provide it. */
record Profile(Integer age, String state, String gender, String socialCategory, String occupation,
		Long annualIncome) {
}

package com.yojnasetu.scheme;

import java.time.Instant;
import java.util.List;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

/**
 * A scheme exactly as stored by the ingestion pipeline. Text fields hold official wording; a null field
 * means the official source did not provide it.
 */
@Document("schemes")
public record Scheme(
		@Id String id,
		String name,
		String shortTitle,
		String description,
		String details,
		String eligibilityText,
		String benefits,
		String documents,
		String applicationProcess,
		String conditions,
		String level,
		String state,
		String ministry,
		String department,
		String implementingAgency,
		List<String> categories,
		List<String> tags,
		List<String> beneficiaryTypes,
		String openDate,
		String closeDate,
		List<Reference> references,
		List<Faq> faqs,
		EligibilityRules eligibility,
		String sourceUrl,
		String sourceName,
		Instant syncedAt) {

	public record Reference(String title, String url) {
	}

	public record Faq(String question, String answer) {
	}

}

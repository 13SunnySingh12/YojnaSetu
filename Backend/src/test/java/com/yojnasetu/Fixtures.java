package com.yojnasetu;

import java.util.Date;
import java.util.List;

import org.bson.Document;
import org.springframework.data.mongodb.core.MongoTemplate;

import com.mongodb.client.model.IndexOptions;

/** MOCK / TEST ONLY: invented schemes shaped like ingestion output (AI/ingestion/store.py). */
public final class Fixtures {

	private Fixtures() {
	}

	public static Document scheme(String id, String name, String level, String state, List<String> categories,
			List<String> tags, String description) {
		return new Document("_id", id).append("name", name)
			.append("description", description)
			.append("eligibilityText", "Official eligibility text of " + id + ".")
			.append("documents", null)
			.append("level", level)
			.append("state", state)
			.append("categories", categories)
			.append("tags", tags)
			.append("beneficiaryTypes", List.of("Individual"))
			.append("eligibility", state == null ? new Document() : new Document("states", List.of(state)))
			.append("sourceUrl", "https://www.myscheme.gov.in/schemes/" + id)
			.append("sourceName", "myScheme")
			.append("nameKey", name.toLowerCase())
			.append("syncedAt", new Date());
	}

	public static void reset(MongoTemplate mongo, List<Document> schemes) {
		mongo.dropCollection("schemes");
		mongo.getCollection("schemes").insertMany(schemes);
		// Mirrors the text index created by the ingestion pipeline.
		mongo.getCollection("schemes").createIndex(
				new Document("name", "text").append("shortTitle", "text").append("tags", "text")
					.append("categories", "text").append("description", "text"),
				new IndexOptions().name("scheme_text").defaultLanguage("english")
					.weights(new Document("name", 10).append("shortTitle", 8).append("tags", 5)
						.append("categories", 3).append("description", 2)));
	}

	public static List<Document> standardSchemes() {
		return List.of(
				scheme("central-pension", "Test Old Age Pension", "Central", null,
						List.of("Social welfare & Empowerment"), List.of("Pension", "Senior Citizen"),
						"Monthly pension for elderly citizens."),
				scheme("bihar-farm", "Test Farmer Support", "State", "Bihar",
						List.of("Agriculture,Rural & Environment"), List.of("Farmer"), "Support for farmers."),
				scheme("kerala-scholar", "Test Merit Scholarship", "State", "Kerala",
						List.of("Education & Learning"), List.of("Scholarship", "Student"), "Scholarship for students."),
				scheme("central-loan", "Test Enterprise Loan", "Central", null,
						List.of("Business & Entrepreneurship"), List.of("Loan", "MSME"), "Loans for small businesses."),
				scheme("jk-housing", "Test Housing Aid", "State", "Jammu & Kashmir", List.of("Housing & Shelter"),
						List.of("Housing"), "Help to build a house."));
	}

}

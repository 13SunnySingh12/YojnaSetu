package com.yojnasetu.eligibility;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.bson.Document;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.assertj.MockMvcTester;

import com.yojnasetu.IntegrationTest;

/** MOCK / TEST ONLY: invented schemes with invented eligibility rules. */
@IntegrationTest
class EligibilityApiTests {

	@Autowired
	MockMvcTester mvc;

	@Autowired
	MongoTemplate mongo;

	static Document scheme(String id, String name, String state, Document eligibility) {
		return new Document("_id", id).append("name", name)
			.append("description", "About " + name)
			.append("level", state == null ? "Central" : "State")
			.append("state", state)
			.append("eligibility", eligibility)
			.append("sourceUrl", "https://www.myscheme.gov.in/schemes/" + id)
			.append("sourceName", "myScheme");
	}

	@BeforeEach
	void seed() {
		mongo.dropCollection("schemes");
		mongo.getCollection("schemes").insertMany(List.of(
				scheme("women-central", "Test Women Enterprise", null,
						new Document("genders", List.of("Female")).append("minAge", 18).append("maxAge", 40)),
				scheme("bihar-state", "Test Bihar Support", "Bihar", new Document("states", List.of("Bihar"))),
				scheme("kerala-state", "Test Kerala Support", "Kerala", new Document("states", List.of("Kerala"))),
				scheme("sc-income", "Test SC Scholarship", null,
						new Document("socialCategories", List.of("Scheduled Caste (SC)"))
							.append("maxAnnualIncome", 250_000L)),
				scheme("open-central", "Test Open Scheme", null, new Document())));
	}

	static final String PROFILE = """
			{"age": 25, "state": "bihar", "gender": "Female", "socialCategory": "SC", "annualIncome": 100000}""";

	@Test
	void shortlistExcludesConflictsAndRanksByMatchedConditions() {
		var json = assertThat(mvc.post().uri("/api/eligibility/check").contentType(MediaType.APPLICATION_JSON)
			.content(PROFILE)).hasStatusOk().bodyJson();
		json.extractingPath("$.results[*].schemeId").asArray()
			.containsExactly("sc-income", "women-central", "bihar-state", "open-central");
		json.extractingPath("$.results[*].status").asArray()
			.containsExactly("LIKELY_MATCH", "LIKELY_MATCH", "LIKELY_MATCH", "MORE_INFO_NEEDED");
		json.extractingPath("$.likelyMatch").asNumber().isEqualTo(3);
		json.extractingPath("$.moreInfoNeeded").asNumber().isEqualTo(1);
		json.extractingPath("$.notAMatch").asNumber().isEqualTo(1);
	}

	@Test
	void missingIncomeIsListedAsInformationNotProvided() {
		assertThat(mvc.post().uri("/api/eligibility/check").contentType(MediaType.APPLICATION_JSON)
			.content("{\"socialCategory\": \"SC\", \"schemeIds\": [\"sc-income\"]}")).hasStatusOk().bodyJson()
			.hasPathSatisfying("$.results[0].status", v -> assertThat(v).asString().isEqualTo("MORE_INFO_NEEDED"))
			.hasPathSatisfying("$.results[0].matched[0].field", v -> assertThat(v).asString().isEqualTo("socialCategory"))
			.hasPathSatisfying("$.results[0].missing[0].requirement",
					v -> assertThat(v).asString().isEqualTo("Annual family income up to ₹2,50,000"));
	}

	@Test
	void requestedSchemesAreReturnedInOrderWithTheReasonForAConflict() {
		assertThat(mvc.post().uri("/api/eligibility/check").contentType(MediaType.APPLICATION_JSON)
			.content("{\"state\": \"Bihar\", \"schemeIds\": [\"kerala-state\", \"bihar-state\", \"nope\"]}"))
			.hasStatusOk().bodyJson()
			.hasPathSatisfying("$.results[*].schemeId",
					v -> assertThat(v).asArray().containsExactly("kerala-state", "bihar-state"))
			.hasPathSatisfying("$.results[0].status", v -> assertThat(v).asString().isEqualTo("NOT_A_MATCH"))
			.hasPathSatisfying("$.results[0].unmatched[0].requirement",
					v -> assertThat(v).asString().isEqualTo("State: Kerala"))
			.hasPathSatisfying("$.results[0].unmatched[0].yourValue",
					v -> assertThat(v).asString().isEqualTo("Bihar"));
	}

	@Test
	void invalidAnswersAreRejectedWithHelpfulMessages() {
		assertThat(mvc.post().uri("/api/eligibility/check").contentType(MediaType.APPLICATION_JSON)
			.content("{\"age\": 150, \"annualIncome\": -5, \"socialCategory\": \"XYZ\"}")).hasStatus(400).bodyJson()
			.extractingPath("$.errors").asArray().hasSize(3);
		assertThat(mvc.post().uri("/api/eligibility/check").contentType(MediaType.APPLICATION_JSON)
			.content("{\"state\": \"Atlantis\"}")).hasStatus(400);
		assertThat(mvc.post().uri("/api/eligibility/check").contentType(MediaType.APPLICATION_JSON)
			.content("{not json")).hasStatus(400);
	}

}

package com.yojnasetu.scheme;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Date;
import java.util.List;

import org.bson.Document;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.http.HttpHeaders;
import org.springframework.test.web.servlet.assertj.MockMvcTester;

import com.mongodb.client.model.IndexOptions;
import com.yojnasetu.IntegrationTest;

/** MOCK / TEST ONLY: the schemes below are invented fixtures, shaped like ingestion output. */
@IntegrationTest
class SchemeApiTests {

	@Autowired
	MockMvcTester mvc;

	@Autowired
	MongoTemplate mongo;

	static Document scheme(String id, String name, String level, String state, List<String> categories,
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

	@BeforeEach
	void seed() {
		mongo.dropCollection("schemes");
		mongo.getCollection("schemes").insertMany(List.of(
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
						List.of("Housing"), "Help to build a house.")));
		// Mirrors the text index created by the ingestion pipeline (AI/ingestion/store.py).
		mongo.getCollection("schemes").createIndex(
				new Document("name", "text").append("shortTitle", "text").append("tags", "text")
					.append("categories", "text").append("description", "text"),
				new IndexOptions().name("scheme_text").defaultLanguage("english")
					.weights(new Document("name", 10).append("shortTitle", 8).append("tags", 5)
						.append("categories", 3).append("description", 2)));
	}

	@Test
	void detailReturnsTheStoredRecordWithExplicitNullsForMissingFields() {
		assertThat(mvc.get().uri("/api/schemes/central-pension")).hasStatusOk().bodyJson()
			.hasPathSatisfying("$.name", v -> assertThat(v).asString().isEqualTo("Test Old Age Pension"))
			.hasPathSatisfying("$.sourceUrl",
					v -> assertThat(v).asString().isEqualTo("https://www.myscheme.gov.in/schemes/central-pension"))
			.hasPathSatisfying("$.eligibilityText", v -> assertThat(v).asString().contains("Official eligibility"))
			.hasPathSatisfying("$.documents", v -> assertThat(v).isNull());
	}

	@Test
	void unknownSchemeIsNotFoundAndMalformedIdIsRejected() {
		assertThat(mvc.get().uri("/api/schemes/no-such-scheme")).hasStatus(404).bodyJson()
			.extractingPath("$.detail").asString().contains("No scheme");
		assertThat(mvc.get().uri("/api/schemes/{id}", "bad id!")).hasStatus(400);
	}

	@Test
	void keywordSearchRanksTheBestMatchFirst() {
		assertThat(mvc.get().uri("/api/schemes?q=pension")).hasStatusOk().bodyJson()
			.hasPathSatisfying("$.items[0].id", v -> assertThat(v).asString().isEqualTo("central-pension"))
			.hasPathSatisfying("$.total", v -> assertThat(v).asNumber().isEqualTo(1));
	}

	@Test
	void categoryBrowsingReturnsOnlyThatCategory() {
		assertThat(mvc.get().uri("/api/schemes").param("category", "Education & Learning")).hasStatusOk().bodyJson()
			.extractingPath("$.items[*].id").asArray().containsExactly("kerala-scholar");
	}

	@Test
	void stateFilterKeepsCentralSchemesAndThatStatesOwn() {
		assertThat(mvc.get().uri("/api/schemes?state=bihar")).hasStatusOk().bodyJson()
			.extractingPath("$.items[*].id").asArray()
			.containsExactlyInAnyOrder("central-pension", "central-loan", "bihar-farm");
	}

	@Test
	void stateFilterMatchesAlternativeOfficialSpellings() {
		assertThat(mvc.get().uri("/api/schemes?state=Jammu and Kashmir&level=State")).hasStatusOk().bodyJson()
			.extractingPath("$.items[*].id").asArray().containsExactly("jk-housing");
	}

	@Test
	void searchByNeedUsesOfficialTagsAndCategories() {
		assertThat(mvc.get().uri("/api/schemes?need=farmer")).hasStatusOk().bodyJson()
			.extractingPath("$.items[*].id").asArray().containsExactly("bihar-farm");
		assertThat(mvc.get().uri("/api/schemes?need=senior-citizen")).hasStatusOk().bodyJson()
			.extractingPath("$.items[*].id").asArray().containsExactly("central-pension");
	}

	@Test
	void browsingIsSortedByNameAndPaginatedWithTotal() {
		assertThat(mvc.get().uri("/api/schemes?size=2&page=1")).hasStatusOk().bodyJson()
			.hasPathSatisfying("$.total", v -> assertThat(v).asNumber().isEqualTo(5))
			.extractingPath("$.items[*].name").asArray()
			.containsExactly("Test Housing Aid", "Test Merit Scholarship");
	}

	@Test
	void invalidParametersAreRejectedWithHelpfulMessages() {
		assertThat(mvc.get().uri("/api/schemes?size=500&age=-1")).hasStatus(400).bodyJson()
			.extractingPath("$.errors").asArray().hasSize(2);
		assertThat(mvc.get().uri("/api/schemes?gender=Other")).hasStatus(400);
		assertThat(mvc.get().uri("/api/schemes?state=Atlantis")).hasStatus(400).bodyJson()
			.extractingPath("$.detail").asString().contains("state");
		assertThat(mvc.get().uri("/api/schemes?need=astronaut")).hasStatus(400);
	}

	@Test
	void filterOptionsCountCategoriesFromStoredData() {
		assertThat(mvc.get().uri("/api/filters")).hasStatusOk().bodyJson()
			.hasPathSatisfying("$.states", v -> assertThat(v).asArray().hasSize(36))
			.hasPathSatisfying("$.needs", v -> assertThat(v).asArray().hasSize(8))
			.hasPathSatisfying("$.beneficiaryTypes", v -> assertThat(v).asArray().containsExactly("Individual"))
			.extractingPath("$.categories[?(@.name == 'Housing & Shelter')].count").asArray().containsExactly(1);
	}

	@Test
	void corsAllowsOnlyTheConfiguredOrigin() {
		assertThat(mvc.options().uri("/api/schemes").header(HttpHeaders.ORIGIN, "http://localhost:5173")
			.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")).hasStatusOk()
			.hasHeader(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:5173");
		assertThat(mvc.options().uri("/api/schemes").header(HttpHeaders.ORIGIN, "https://evil.example")
			.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")).hasStatus(403);
	}

}

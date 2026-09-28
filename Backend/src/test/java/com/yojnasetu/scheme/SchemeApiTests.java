package com.yojnasetu.scheme;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.http.HttpHeaders;

import com.yojnasetu.Fixtures;
import com.yojnasetu.IntegrationTestSupport;

/** MOCK / TEST ONLY: the schemes below are invented fixtures, shaped like ingestion output. */
class SchemeApiTests extends IntegrationTestSupport {

	@Autowired
	MongoTemplate mongo;

	@BeforeEach
	void seed() {
		Fixtures.reset(mongo, Fixtures.standardSchemes());
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
		// The reason is readable; the id pattern itself is never shown to people.
		assertThat(mvc.get().uri("/api/schemes/{id}", "bad id!")).hasStatus(400).bodyJson()
			.extractingPath("$.errors[0]").asString().isEqualTo("id: is not a valid scheme link");
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
			.hasPathSatisfying("$.occupations", v -> assertThat(v).asArray().isEmpty())
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

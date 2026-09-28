package com.yojnasetu.ai;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.http.MediaType;

import com.yojnasetu.FakeAiServer;
import com.yojnasetu.Fixtures;
import com.yojnasetu.IntegrationTestSupport;

/** MOCK / TEST ONLY: AI service replies come from {@link FakeAiServer}. */
class AiApiTests extends IntegrationTestSupport {

	@Autowired
	MongoTemplate mongo;

	@BeforeEach
	void seed() {
		Fixtures.reset(mongo, Fixtures.standardSchemes());
	}

	@Test
	void searchMergesKeywordAndMeaningResultsAndSendsTheInternalToken() {
		FakeAiServer.respond("/search", """
				{"results": [{"schemeId": "kerala-scholar", "score": 0.9}, {"schemeId": "central-pension", "score": 0.8}]}""");
		var json = assertThat(mvc.get().uri("/api/search?q=pension")).hasStatusOk().bodyJson();
		json.extractingPath("$.items[*].scheme.id").asArray().containsExactly("central-pension", "kerala-scholar");
		json.extractingPath("$.items[0].matchedByKeyword").isEqualTo(true);
		json.extractingPath("$.items[0].matchedByMeaning").isEqualTo(true);
		json.extractingPath("$.items[1].matchedByKeyword").isEqualTo(false);
		json.extractingPath("$.semanticAvailable").isEqualTo(true);
		json.extractingPath("$.total").asNumber().isEqualTo(2);
		assertThat(FakeAiServer.requests()).singleElement()
			.satisfies(r -> assertThat(r.token()).isEqualTo("test-token"))
			// uvicorn does not support the h2c upgrade and drops the POST body (found in a live run)
			.satisfies(r -> assertThat(r.upgrade()).isNull())
			.satisfies(r -> assertThat(r.body()).contains("\"query\":\"pension\""));
	}

	@Test
	void searchStillAnswersWithKeywordResultsWhenTheAiServiceIsDown() {
		assertThat(mvc.get().uri("/api/search?q=pension")).hasStatusOk().bodyJson()
			.hasPathSatisfying("$.items[*].scheme.id", v -> assertThat(v).asArray().containsExactly("central-pension"))
			.hasPathSatisfying("$.semanticAvailable", v -> assertThat(v).isEqualTo(false));
	}

	@Test
	void malformedAiResponsesCountAsUnavailable() {
		FakeAiServer.respond("/search", "{not json");
		assertThat(mvc.get().uri("/api/search?q=pension")).hasStatusOk().bodyJson()
			.extractingPath("$.semanticAvailable").isEqualTo(false);
	}

	@Test
	void searchQueryIsValidated() {
		assertThat(mvc.get().uri("/api/search?q=a")).hasStatus(400);
		assertThat(mvc.get().uri("/api/search")).hasStatus(400);
	}

	@Test
	void relatedSchemesKeepTheAiOrderAndDegradeToEmpty() {
		FakeAiServer.respond("/related", """
				{"results": [{"schemeId": "central-loan", "score": 0.9}, {"schemeId": "bihar-farm", "score": 0.8}]}""");
		assertThat(mvc.get().uri("/api/schemes/central-pension/related")).hasStatusOk().bodyJson()
			.extractingPath("$.items[*].id").asArray().containsExactly("central-loan", "bihar-farm");
		FakeAiServer.reset();
		assertThat(mvc.get().uri("/api/schemes/central-pension/related")).hasStatusOk().bodyJson()
			.hasPathSatisfying("$.items", v -> assertThat(v).asArray().isEmpty())
			.hasPathSatisfying("$.available", v -> assertThat(v).isEqualTo(false));
	}

	@Test
	void askReturnsTheGroundedAnswerWithSources() {
		FakeAiServer.respond("/ask", """
				{"answer": "It gives a monthly pension.", "grounded": true, "provider": "gemini",
				 "sources": [{"schemeId": "central-pension", "name": "Test Old Age Pension",
				              "sourceUrl": "https://www.myscheme.gov.in/schemes/central-pension"}]}""");
		assertThat(mvc.post().uri("/api/ask").header("X-Forwarded-For", newClient())
			.contentType(MediaType.APPLICATION_JSON).content("{\"question\": \"What does the pension give?\"}"))
			.hasStatusOk().bodyJson()
			.hasPathSatisfying("$.answer", v -> assertThat(v).asString().isEqualTo("It gives a monthly pension."))
			.hasPathSatisfying("$.grounded", v -> assertThat(v).isEqualTo(true))
			.hasPathSatisfying("$.sources[0].sourceUrl", v -> assertThat(v).asString().startsWith("https://www.myscheme.gov.in/"))
			.doesNotHavePath("$.provider");
	}

	@Test
	void askExplainsPoliteWhenTheAiServiceIsDown() {
		assertThat(mvc.post().uri("/api/ask").header("X-Forwarded-For", newClient())
			.contentType(MediaType.APPLICATION_JSON).content("{\"question\": \"What does the pension give?\"}"))
			.hasStatus(503).bodyJson()
			.extractingPath("$.detail").asString().contains("Keyword search, scheme details and eligibility checks still work");
	}

	@Test
	void askValidatesTheQuestion() {
		assertThat(mvc.post().uri("/api/ask").header("X-Forwarded-For", newClient())
			.contentType(MediaType.APPLICATION_JSON).content("{\"question\": \"hi\"}")).hasStatus(400);
		assertThat(FakeAiServer.requests()).isEmpty();
	}

	@Test
	void explainSendsTheStoredOfficialTextAndReturnsItAlongside() {
		FakeAiServer.respond("/explain", "{\"explanation\": \"You must meet these rules.\", \"provider\": \"groq\"}");
		assertThat(mvc.post().uri("/api/schemes/central-pension/explain").header("X-Forwarded-For", newClient())
			.contentType(MediaType.APPLICATION_JSON).content("{\"section\": \"eligibilityText\"}"))
			.hasStatusOk().bodyJson()
			.hasPathSatisfying("$.original", v -> assertThat(v).asString().isEqualTo("Official eligibility text of central-pension."))
			.hasPathSatisfying("$.explanation", v -> assertThat(v).asString().isEqualTo("You must meet these rules."));
		assertThat(FakeAiServer.requests()).singleElement()
			.satisfies(r -> assertThat(r.body()).contains("Official eligibility text of central-pension.")
				.contains("\"section\":\"Eligibility criteria\""));
	}

	@Test
	void explainingAMissingSectionSaysItIsNotAvailableWithoutCallingTheAi() {
		assertThat(mvc.post().uri("/api/schemes/central-pension/explain").header("X-Forwarded-For", newClient())
			.contentType(MediaType.APPLICATION_JSON).content("{\"section\": \"documents\"}"))
			.hasStatus(404).bodyJson()
			.extractingPath("$.detail").asString().isEqualTo("Not available from the official source.");
		assertThat(FakeAiServer.requests()).isEmpty();
		assertThat(mvc.post().uri("/api/schemes/central-pension/explain")
			.contentType(MediaType.APPLICATION_JSON).content("{\"section\": \"sourceUrl\"}")).hasStatus(400);
	}

	@Test
	void eligibilityExplanationDescribesTheEngineOutcomeComputedOnTheServer() {
		FakeAiServer.respond("/explain-eligibility", "{\"explanation\": \"This is a Bihar scheme; you live in Kerala.\"}");
		assertThat(mvc.post().uri("/api/eligibility/explain").header("X-Forwarded-For", newClient())
			.contentType(MediaType.APPLICATION_JSON).content("{\"state\": \"Kerala\", \"schemeIds\": [\"bihar-farm\"]}"))
			.hasStatusOk().bodyJson()
			.hasPathSatisfying("$.status", v -> assertThat(v).asString().isEqualTo("NOT_A_MATCH"))
			.hasPathSatisfying("$.explanation", v -> assertThat(v).asString().contains("Bihar"));
		assertThat(FakeAiServer.requests()).singleElement()
			.satisfies(r -> assertThat(r.body()).contains("\"status\":\"NOT_A_MATCH\"").contains("State: Bihar"));
	}

	@Test
	void aiEndpointsAreRateLimitedPerClient() throws InterruptedException {
		FakeAiServer.respond("/ask", "{\"answer\": \"ok\", \"grounded\": true, \"sources\": []}");
		// Limits count per calendar minute; start where all six requests fall in the same minute
		// (a run that straddled a minute boundary failed in CI).
		long untilNextMinute = 60_000 - System.currentTimeMillis() % 60_000;
		if (untilNextMinute < 5_000) {
			Thread.sleep(untilNextMinute);
		}
		String client = newClient();
		for (int i = 0; i < 5; i++) {
			assertThat(mvc.post().uri("/api/ask").header("X-Forwarded-For", client)
				.contentType(MediaType.APPLICATION_JSON).content("{\"question\": \"Question number " + i + "\"}"))
				.hasStatusOk();
		}
		assertThat(mvc.post().uri("/api/ask").header("X-Forwarded-For", client)
			.contentType(MediaType.APPLICATION_JSON).content("{\"question\": \"One too many\"}")).hasStatus(429);
	}

}

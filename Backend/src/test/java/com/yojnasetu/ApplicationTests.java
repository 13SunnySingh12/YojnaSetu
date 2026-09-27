package com.yojnasetu;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

class ApplicationTests extends IntegrationTestSupport {

	@Test
	void healthReportsUpWhenTheDatabaseIsReachable() {
		assertThat(mvc.get().uri("/actuator/health")).hasStatusOk()
			.bodyJson().extractingPath("$.status").isEqualTo("UP");
	}

	@Test
	void unknownRoutesAnswerWithProblemDetailAndNoInternals() {
		assertThat(mvc.get().uri("/api/does-not-exist")).hasStatus(404)
			.hasContentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON)
			.bodyText().doesNotContain("trace", "Exception");
	}

}

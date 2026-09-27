package com.yojnasetu;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.assertj.MockMvcTester;

@IntegrationTest
class ApplicationTests {

	@Autowired
	MockMvcTester mvc;

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

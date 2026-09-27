package com.yojnasetu;

import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.assertj.MockMvcTester;

/**
 * Full application against a real MongoDB container and the fake AI service, driven through MockMvc.
 * All subclasses share one application context and one container.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Import(TestcontainersConfiguration.class)
// Pinned here so a developer's .env can never leak into tests. The container's service connection
// replaces MONGODB_URI; it only satisfies the required placeholder.
@TestPropertySource(properties = { "MONGODB_URI=mongodb://replaced-by-testcontainers",
		"MONGODB_DATABASE=yojnasetu_test", "ALLOWED_ORIGINS=http://localhost:5173", "AI_SERVICE_TOKEN=test-token",
		"AI_REQUESTS_PER_CLIENT_PER_MINUTE=5", "AI_REQUESTS_PER_MINUTE=100000" })
public abstract class IntegrationTestSupport {

	private static final AtomicInteger clients = new AtomicInteger();

	@Autowired
	protected MockMvcTester mvc;

	@DynamicPropertySource
	static void aiService(DynamicPropertyRegistry registry) {
		registry.add("app.ai-service-url", FakeAiServer::url);
	}

	@BeforeEach
	void resetFakeAi() {
		FakeAiServer.reset();
	}

	/** A fresh client address, so per-client rate limits never leak between tests. */
	protected static String newClient() {
		int n = clients.incrementAndGet();
		return "198.51." + (n / 250) + "." + (n % 250 + 1);
	}

}

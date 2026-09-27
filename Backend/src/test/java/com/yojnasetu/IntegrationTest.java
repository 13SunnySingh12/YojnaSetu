package com.yojnasetu;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;

/** Full application against a real MongoDB container, driven through MockMvc. */
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@SpringBootTest
@AutoConfigureMockMvc
@Import(TestcontainersConfiguration.class)
// The container's service connection replaces this; it only satisfies the required placeholder.
// Pinned here so a developer's .env can never leak into tests.
@TestPropertySource(properties = { "MONGODB_URI=mongodb://replaced-by-testcontainers",
		"MONGODB_DATABASE=yojnasetu_test", "ALLOWED_ORIGINS=http://localhost:5173",
		"AI_SERVICE_URL=http://localhost:1", "AI_SERVICE_TOKEN=test-token" })
public @interface IntegrationTest {
}

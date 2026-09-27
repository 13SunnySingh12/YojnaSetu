package com.yojnasetu.ai;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

import com.yojnasetu.config.AppProperties;

/** Calls the FastAPI AI service. Every failure surfaces as {@link Unavailable} so callers can degrade. */
@Component
public class AiClient {

	private static final Logger log = LoggerFactory.getLogger(AiClient.class);

	private final RestClient http;

	private final boolean configured;

	AiClient(AppProperties properties, RestClient.Builder builder) {
		this.configured = StringUtils.hasText(properties.aiServiceToken());
		if (!configured) {
			log.warn("AI_SERVICE_TOKEN is not set: AI features are disabled");
		}
		// HTTP/1.1: over plain http the JDK client otherwise attempts an h2c upgrade, which uvicorn does not
		// support, and the POST body is lost (the AI service then answers 422).
		var factory = new JdkClientHttpRequestFactory(HttpClient.newBuilder()
			.version(HttpClient.Version.HTTP_1_1)
			.connectTimeout(Duration.ofSeconds(3))
			.build());
		// Covers the AI service's own worst case: query embedding plus two generation attempts.
		factory.setReadTimeout(Duration.ofSeconds(45));
		this.http = builder.baseUrl(properties.aiServiceUrl())
			.defaultHeader("X-Internal-Token", configured ? properties.aiServiceToken() : "")
			.requestFactory(factory)
			.build();
	}

	public record Scored(String schemeId, double score) {
	}

	public record Source(String schemeId, String name, String sourceUrl) {
	}

	public record Answer(String answer, boolean grounded, List<Source> sources) {
	}

	record Results(List<Scored> results) {
	}

	record Explanation(String explanation) {
	}

	record SearchBody(String query, int limit) {
	}

	record RelatedBody(String schemeId, int limit) {
	}

	record AskBody(String question, String schemeId) {
	}

	record ExplainBody(String schemeName, String section, String text) {
	}

	record EligibilityBody(String schemeName, String status, List<?> matched, List<?> unmatched, List<?> missing) {
	}

	public List<Scored> search(String query, int limit) {
		return call("/search", new SearchBody(query, limit), Results.class).results();
	}

	public List<Scored> related(String schemeId, int limit) {
		return call("/related", new RelatedBody(schemeId, limit), Results.class).results();
	}

	public Answer ask(String question, String schemeId) {
		return call("/ask", new AskBody(question, schemeId), Answer.class);
	}

	/** Plain-language version of official text, or null when the model found it unclear. */
	public String explain(String schemeName, String section, String text) {
		return call("/explain", new ExplainBody(schemeName, section, text), Explanation.class).explanation();
	}

	public String explainEligibility(String schemeName, String status, List<?> matched, List<?> unmatched,
			List<?> missing) {
		return call("/explain-eligibility", new EligibilityBody(schemeName, status, matched, unmatched, missing),
				Explanation.class).explanation();
	}

	private <T> T call(String path, Object body, Class<T> type) {
		if (!configured) {
			throw new Unavailable();
		}
		try {
			T result = http.post().uri(path).contentType(MediaType.APPLICATION_JSON).body(body).retrieve().body(type);
			if (result == null) {
				throw new Unavailable();
			}
			return result;
		}
		catch (HttpClientErrorException ex) {
			// A 4xx is our fault (token or request contract), not an outage: make it loud in the logs.
			log.error("AI service rejected {} with {}; check AI_SERVICE_TOKEN and the request contract", path,
					ex.getStatusCode());
			throw new Unavailable();
		}
		catch (RestClientException ex) {
			log.warn("AI service call {} failed: {}", path, ex.getMessage());
			throw new Unavailable();
		}
	}

	public static class Unavailable extends ResponseStatusException {

		Unavailable() {
			super(HttpStatus.SERVICE_UNAVAILABLE, "The AI assistant is unavailable right now. Keyword search, "
					+ "scheme details and eligibility checks still work.");
		}

	}

}

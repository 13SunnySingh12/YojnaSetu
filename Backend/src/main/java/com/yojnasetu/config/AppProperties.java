package com.yojnasetu.config;

import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * @param allowedOrigins browser origins allowed to call the API (CORS)
 * @param aiServiceUrl base URL of the FastAPI AI service
 * @param aiServiceToken shared secret sent to the AI service; blank disables AI features
 */
@ConfigurationProperties("app")
public record AppProperties(List<String> allowedOrigins, String aiServiceUrl, String aiServiceToken) {
}

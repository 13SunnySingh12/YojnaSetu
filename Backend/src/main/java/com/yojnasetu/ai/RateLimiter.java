package com.yojnasetu.ai;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

import jakarta.servlet.http.HttpServletRequest;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

import com.yojnasetu.config.AppProperties;

/**
 * Fixed one-minute windows per client and in total, protecting the LLM budget from abuse.
 * Known limit: counts live in memory on a single instance; move them to a shared store if the backend is
 * scaled out.
 */
@Component
public class RateLimiter {

	private static final String GLOBAL = "*";

	private final int perClient;

	private final int total;

	private final Map<String, Window> windows = new ConcurrentHashMap<>();

	private record Window(long minute, AtomicInteger count) {
	}

	RateLimiter(AppProperties properties) {
		this.perClient = properties.aiRequestsPerClientPerMinute();
		this.total = properties.aiRequestsPerMinute();
	}

	public void check(HttpServletRequest request) {
		long minute = System.currentTimeMillis() / 60_000;
		// Per-client first, so a client that is over its own limit does not use up the shared budget.
		if (!allow(clientKey(request), minute, perClient) || !allow(GLOBAL, minute, total)) {
			throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS,
					"Too many AI requests. Please wait a minute and try again.");
		}
	}

	private boolean allow(String key, long minute, int limit) {
		if (windows.size() > 10_000) {
			windows.values().removeIf(w -> w.minute() < minute);
		}
		Window window = windows.compute(key,
				(k, old) -> old == null || old.minute() != minute ? new Window(minute, new AtomicInteger()) : old);
		return window.count().incrementAndGet() <= limit;
	}

	/** The last X-Forwarded-For entry is the one added by the hosting proxy; earlier ones are client-supplied. */
	static String clientKey(HttpServletRequest request) {
		String forwarded = request.getHeader("X-Forwarded-For");
		if (forwarded != null && !forwarded.isBlank()) {
			String[] hops = forwarded.split(",");
			return hops[hops.length - 1].trim();
		}
		return request.getRemoteAddr();
	}

}

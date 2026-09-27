package com.yojnasetu.ai;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.web.server.ResponseStatusException;

import com.yojnasetu.config.AppProperties;

class RateLimiterTests {

	static RateLimiter limiter(int perClient, int total) {
		return new RateLimiter(new AppProperties(List.of(), "http://ai", "t", perClient, total));
	}

	static MockHttpServletRequest from(String forwardedFor) {
		MockHttpServletRequest request = new MockHttpServletRequest();
		request.setRemoteAddr("10.0.0.1");
		if (forwardedFor != null) {
			request.addHeader("X-Forwarded-For", forwardedFor);
		}
		return request;
	}

	@Test
	void eachClientGetsItsOwnAllowance() {
		RateLimiter limiter = limiter(2, 100);
		limiter.check(from("1.1.1.1"));
		limiter.check(from("1.1.1.1"));
		assertThatThrownBy(() -> limiter.check(from("1.1.1.1"))).isInstanceOf(ResponseStatusException.class)
			.hasMessageContaining("Too many AI requests");
		assertThatCode(() -> limiter.check(from("2.2.2.2"))).doesNotThrowAnyException();
	}

	@Test
	void theTotalBudgetCapsAllClientsTogether() {
		RateLimiter limiter = limiter(10, 2);
		limiter.check(from("1.1.1.1"));
		limiter.check(from("2.2.2.2"));
		assertThatThrownBy(() -> limiter.check(from("3.3.3.3"))).isInstanceOf(ResponseStatusException.class);
	}

	@Test
	void aRejectedClientDoesNotSpendTheSharedBudget() {
		RateLimiter limiter = limiter(1, 2);
		limiter.check(from("1.1.1.1"));
		for (int i = 0; i < 5; i++) {
			assertThatThrownBy(() -> limiter.check(from("1.1.1.1"))).isInstanceOf(ResponseStatusException.class);
		}
		assertThatCode(() -> limiter.check(from("2.2.2.2"))).doesNotThrowAnyException();
	}

	@Test
	void clientIsTheHopAddedByTheProxyNotAClientSuppliedOne() {
		assertThat(RateLimiter.clientKey(from("6.6.6.6, 203.0.113.7"))).isEqualTo("203.0.113.7");
		assertThat(RateLimiter.clientKey(from(null))).isEqualTo("10.0.0.1");
	}

}

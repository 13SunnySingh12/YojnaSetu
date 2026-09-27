package com.yojnasetu.eligibility;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.yojnasetu.eligibility.EligibilityEngine.Condition;
import com.yojnasetu.eligibility.EligibilityEngine.Outcome;
import com.yojnasetu.eligibility.EligibilityEngine.Status;
import com.yojnasetu.scheme.IndianStates;
import com.yojnasetu.scheme.Scheme;
import com.yojnasetu.scheme.SchemeRepository;

/** Eligibility guidance. The result is guidance only; the concerned department decides eligibility. */
@RestController
@RequestMapping("/api/eligibility")
class EligibilityController {

	static final int MAX_RESULTS = 50;

	private final SchemeRepository schemes;

	EligibilityController(SchemeRepository schemes) {
		this.schemes = schemes;
	}

	record CheckRequest(@Min(0) @Max(120) Integer age, @Size(max = 60) String state,
			@Pattern(regexp = "Male|Female|Transgender") String gender,
			@Pattern(regexp = "General|OBC|SC|ST") String socialCategory, @Size(max = 80) String occupation,
			@PositiveOrZero @Max(1_000_000_000L) Long annualIncome,
			@Size(max = 10) List<@Pattern(regexp = "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$") String> schemeIds) {
	}

	record SchemeResult(String schemeId, String name, String description, String level, String state,
			String sourceUrl, Status status, List<Condition> matched, List<Condition> unmatched,
			List<Condition> missing) {
	}

	/** Counts cover every scheme checked; {@code results} is the shortlist (or the requested schemes). */
	record CheckResponse(List<SchemeResult> results, long likelyMatch, long moreInfoNeeded, long notAMatch) {
	}

	@PostMapping("/check")
	CheckResponse check(@Valid @RequestBody CheckRequest request) {
		Profile profile = new Profile(request.age(), IndianStates.requireCanonical(request.state()),
				request.gender(), request.socialCategory(),
				StringUtils.hasText(request.occupation()) ? request.occupation().trim() : null, request.annualIncome());
		boolean specific = request.schemeIds() != null && !request.schemeIds().isEmpty();
		List<Scheme> candidates = specific ? schemes.findAllById(request.schemeIds()) : schemes.findForEligibility();
		List<SchemeResult> results = candidates.stream().map(s -> result(s, profile)).toList();

		Map<Status, Long> counts = results.stream()
			.collect(Collectors.groupingBy(SchemeResult::status, Collectors.counting()));
		List<SchemeResult> shown;
		if (specific) {
			Map<String, SchemeResult> byId = results.stream()
				.collect(Collectors.toMap(SchemeResult::schemeId, Function.identity()));
			shown = request.schemeIds().stream().distinct().map(byId::get).filter(r -> r != null).toList();
		}
		else {
			// Recommendations: schemes that do not conflict with the answers, most matched conditions first.
			shown = results.stream()
				.filter(r -> r.status() != Status.NOT_A_MATCH)
				.sorted(Comparator.comparingInt((SchemeResult r) -> -r.matched().size())
					.thenComparing(r -> r.status() == Status.LIKELY_MATCH ? 0 : 1)
					.thenComparingInt(r -> r.missing().size())
					.thenComparing(SchemeResult::name, String.CASE_INSENSITIVE_ORDER))
				.limit(MAX_RESULTS)
				.toList();
		}
		return new CheckResponse(shown, counts.getOrDefault(Status.LIKELY_MATCH, 0L),
				counts.getOrDefault(Status.MORE_INFO_NEEDED, 0L), counts.getOrDefault(Status.NOT_A_MATCH, 0L));
	}

	private static SchemeResult result(Scheme scheme, Profile profile) {
		Outcome outcome = EligibilityEngine.evaluate(scheme.eligibility(), profile);
		return new SchemeResult(scheme.id(), scheme.name(), scheme.description(), scheme.level(), scheme.state(),
				scheme.sourceUrl(), outcome.status(), outcome.matched(), outcome.unmatched(), outcome.missing());
	}

}

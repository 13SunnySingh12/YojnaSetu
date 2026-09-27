package com.yojnasetu.ai;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import com.yojnasetu.scheme.Scheme;
import com.yojnasetu.scheme.SchemeFilter;
import com.yojnasetu.scheme.SchemeRepository;
import com.yojnasetu.scheme.SchemeSummary;

@RestController
@RequestMapping("/api")
class AiController {

	static final String SCHEME_ID = "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$";

	static final int CANDIDATES = 50;

	/** Explainable sections of a scheme and the heading the model sees for each. */
	static final Map<String, String> SECTIONS = Map.of("description", "Description", "details", "Details",
			"eligibilityText", "Eligibility criteria", "benefits", "Benefits", "documents", "Required documents",
			"applicationProcess", "Application process", "conditions", "Important conditions");

	private final SchemeRepository schemes;

	private final AiClient ai;

	private final RateLimiter rateLimiter;

	AiController(SchemeRepository schemes, AiClient ai, RateLimiter rateLimiter) {
		this.schemes = schemes;
		this.ai = ai;
		this.rateLimiter = rateLimiter;
	}

	record SearchHit(SchemeSummary scheme, boolean matchedByKeyword, boolean matchedByMeaning) {
	}

	record SearchResponse(List<SearchHit> items, int page, int size, long total, boolean semanticAvailable) {
	}

	/** One search box: keyword and meaning-based results merged, de-duplicated and ranked together. */
	@GetMapping("/search")
	SearchResponse search(@RequestParam @NotBlank @Size(min = 2, max = 200) String q,
			@RequestParam(defaultValue = "0") @Min(0) @Max(4) int page,
			@RequestParam(defaultValue = "20") @Min(1) @Max(25) int size) {
		String query = q.trim();
		List<String> keyword = schemes.search(new SchemeFilter(query, null, null, null, null, null, null, null), 0,
				CANDIDATES).items().stream().map(SchemeSummary::id).toList();
		List<String> meaning = List.of();
		boolean semanticAvailable = true;
		try {
			meaning = ai.search(query, CANDIDATES).stream().map(AiClient.Scored::schemeId).toList();
		}
		catch (AiClient.Unavailable ex) {
			semanticAvailable = false; // keyword results still answer the search
		}
		List<RankFusion.Fused> fused = RankFusion.fuse(keyword, meaning);
		List<RankFusion.Fused> pageItems = fused.stream().skip((long) page * size).limit(size).toList();
		Map<String, SchemeSummary> summaries = byId(schemes.findSummaries(pageItems.stream().map(RankFusion.Fused::id).toList()));
		List<SearchHit> items = pageItems.stream()
			.filter(f -> summaries.containsKey(f.id()))
			.map(f -> new SearchHit(summaries.get(f.id()), f.keyword(), f.meaning()))
			.toList();
		return new SearchResponse(items, page, size, fused.size(), semanticAvailable);
	}

	record RelatedResponse(List<SchemeSummary> items, boolean available) {
	}

	@GetMapping("/schemes/{id}/related")
	RelatedResponse related(@PathVariable @Pattern(regexp = SCHEME_ID) String id) {
		try {
			List<String> ids = ai.related(id, 5).stream().map(AiClient.Scored::schemeId).toList();
			return new RelatedResponse(schemes.findSummaries(ids), true);
		}
		catch (AiClient.Unavailable ex) {
			return new RelatedResponse(List.of(), false);
		}
	}

	record AskRequest(@NotBlank @Size(min = 3, max = 500) String question,
			@Pattern(regexp = SCHEME_ID) String schemeId) {
	}

	/** Question answering grounded in stored scheme text (RAG in the AI service). */
	@PostMapping("/ask")
	AiClient.Answer ask(@Valid @RequestBody AskRequest request, HttpServletRequest http) {
		rateLimiter.check(http);
		return ai.ask(request.question().trim(), request.schemeId());
	}

	record ExplainRequest(@NotBlank @Pattern(regexp = "description|details|eligibilityText|benefits|documents"
			+ "|applicationProcess|conditions") String section) {
	}

	record ExplainResponse(String section, String original, String explanation) {
	}

	/** "Explain simply": the official text of one section rewritten in plain words; the original stays. */
	@PostMapping("/schemes/{id}/explain")
	ExplainResponse explain(@PathVariable @Pattern(regexp = SCHEME_ID) String id,
			@Valid @RequestBody ExplainRequest request, HttpServletRequest http) {
		Scheme scheme = schemes.findById(id)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "No scheme exists with this id."));
		String original = sectionText(scheme, request.section());
		if (original == null || original.isBlank()) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Not available from the official source.");
		}
		rateLimiter.check(http);
		String explanation = ai.explain(scheme.name(), SECTIONS.get(request.section()), original);
		return new ExplainResponse(request.section(), original, explanation);
	}

	private static String sectionText(Scheme s, String section) {
		return switch (section) {
			case "description" -> s.description();
			case "details" -> s.details();
			case "eligibilityText" -> s.eligibilityText();
			case "benefits" -> s.benefits();
			case "documents" -> s.documents();
			case "applicationProcess" -> s.applicationProcess();
			case "conditions" -> s.conditions();
			default -> null;
		};
	}

	private static Map<String, SchemeSummary> byId(List<SchemeSummary> summaries) {
		return summaries.stream().collect(Collectors.toMap(SchemeSummary::id, s -> s));
	}

}

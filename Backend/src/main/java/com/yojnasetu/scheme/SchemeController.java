package com.yojnasetu.scheme;

import java.util.List;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import org.springframework.http.HttpStatus;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api")
class SchemeController {

	static final String SCHEME_ID = "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$";

	static final List<String> GENDERS = List.of("Male", "Female", "Transgender");

	private final SchemeRepository repository;

	SchemeController(SchemeRepository repository) {
		this.repository = repository;
	}

	/** Keyword search, category browsing, filters and search by need, all on stored scheme fields. */
	@GetMapping("/schemes")
	PageResult<SchemeSummary> list(@RequestParam(required = false) @Size(max = 200) String q,
			@RequestParam(required = false) @Size(max = 120) String category,
			@RequestParam(required = false) @Size(max = 60) String state,
			@RequestParam(required = false) @Pattern(regexp = "Male|Female|Transgender") String gender,
			@RequestParam(required = false) @Min(0) @Max(120) Integer age,
			@RequestParam(required = false) @Size(max = 60) String beneficiaryType,
			@RequestParam(required = false) @Pattern(regexp = "Central|State") String level,
			@RequestParam(required = false) @Size(max = 40) String need,
			@RequestParam(defaultValue = "0") @Min(0) @Max(500) int page,
			@RequestParam(defaultValue = "20") @Min(1) @Max(50) int size) {
		SchemeFilter filter = new SchemeFilter(blankToNull(q), blankToNull(category), canonicalState(state),
				blankToNull(gender), age, blankToNull(beneficiaryType), blankToNull(level), knownNeed(need));
		return repository.search(filter, page, size);
	}

	@GetMapping("/schemes/{id}")
	Scheme detail(@PathVariable @Pattern(regexp = SCHEME_ID) String id) {
		return repository.findById(id)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "No scheme exists with this id."));
	}

	@GetMapping("/filters")
	FilterOptions filters() {
		return new FilterOptions(repository.categoryCounts(), IndianStates.ALL, repository.beneficiaryTypes(),
				Needs.options(), GENDERS, List.of("Central", "State"));
	}

	record FilterOptions(List<SchemeRepository.CategoryCount> categories, List<String> states,
			List<String> beneficiaryTypes, List<Needs.Option> needs, List<String> genders, List<String> levels) {
	}

	static String canonicalState(String state) {
		if (!StringUtils.hasText(state)) {
			return null;
		}
		return IndianStates.canonical(state)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST,
					"state: not a recognised Indian state or union territory."));
	}

	private static String knownNeed(String need) {
		if (!StringUtils.hasText(need)) {
			return null;
		}
		if (Needs.fromKey(need) == null) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "need: choose one of the listed situations.");
		}
		return need;
	}

	private static String blankToNull(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}

}

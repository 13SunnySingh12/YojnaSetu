package com.yojnasetu.scheme;

import static org.springframework.data.mongodb.core.aggregation.Aggregation.group;
import static org.springframework.data.mongodb.core.aggregation.Aggregation.newAggregation;
import static org.springframework.data.mongodb.core.aggregation.Aggregation.project;
import static org.springframework.data.mongodb.core.aggregation.Aggregation.sort;
import static org.springframework.data.mongodb.core.aggregation.Aggregation.unwind;
import static org.springframework.data.mongodb.core.query.Criteria.where;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.regex.Pattern;

import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.TextCriteria;
import org.springframework.data.mongodb.core.query.TextQuery;
import org.springframework.stereotype.Repository;
import org.springframework.util.StringUtils;

/** All reads of the {@code schemes} collection. Indexes are owned by the ingestion pipeline. */
@Repository
public class SchemeRepository {

	private static final String COLLECTION = "schemes";

	private final MongoTemplate mongo;

	SchemeRepository(MongoTemplate mongo) {
		this.mongo = mongo;
	}

	public Optional<Scheme> findById(String id) {
		return Optional.ofNullable(mongo.findById(id, Scheme.class));
	}

	/** Summaries for the given ids, in the order of the ids; unknown ids are skipped. */
	public List<SchemeSummary> findSummaries(List<String> ids) {
		Query query = new Query(where("_id").in(ids));
		query.fields().include(SchemeSummary.FIELDS);
		var byId = new HashMap<String, SchemeSummary>();
		mongo.find(query, SchemeSummary.class, COLLECTION).forEach(s -> byId.put(s.id(), s));
		return ids.stream().map(byId::get).filter(Objects::nonNull).toList();
	}

	public List<Scheme> findAllById(Collection<String> ids) {
		return mongo.find(new Query(where("_id").in(ids)), Scheme.class);
	}

	/** Keyword search (text index, best match first) or filtered browsing (by name) with pagination. */
	public PageResult<SchemeSummary> search(SchemeFilter filter, int page, int size) {
		Query query = StringUtils.hasText(filter.q())
				? TextQuery.queryText(TextCriteria.forDefaultLanguage().matching(filter.q())).sortByScore()
				: new Query().with(Sort.by("name"));
		List<Criteria> conditions = conditions(filter);
		if (!conditions.isEmpty()) {
			query.addCriteria(new Criteria().andOperator(conditions));
		}
		long total = mongo.count(query, COLLECTION);
		query.with(PageRequest.of(page, size)).fields().include(SchemeSummary.FIELDS);
		return new PageResult<>(mongo.find(query, SchemeSummary.class, COLLECTION), page, size, total);
	}

	/** Candidates for eligibility checks, narrowed by the database where a condition is unambiguous. */
	public List<Scheme> findForEligibility(String canonicalState) {
		Query query = new Query();
		if (canonicalState != null) {
			query.addCriteria(new Criteria().orOperator(where("state").isNull(),
					where("state").regex(IndianStates.labelPattern(canonicalState))));
		}
		query.fields().include("name", "description", "level", "state", "ministry", "categories", "tags",
				"eligibility", "eligibilityText", "sourceUrl", "sourceName");
		return mongo.find(query, Scheme.class);
	}

	public List<CategoryCount> categoryCounts() {
		var aggregation = newAggregation(unwind("categories"), group("categories").count().as("count"),
				project("count").and("name").previousOperation(), sort(Sort.Direction.DESC, "count"));
		return mongo.aggregate(aggregation, COLLECTION, CategoryCount.class).getMappedResults();
	}

	public List<String> beneficiaryTypes() {
		return mongo.findDistinct(new Query(), "beneficiaryTypes", COLLECTION, String.class).stream()
			.sorted()
			.toList();
	}

	public record CategoryCount(String name, long count) {
	}

	private static List<Criteria> conditions(SchemeFilter f) {
		List<Criteria> c = new ArrayList<>();
		if (StringUtils.hasText(f.category())) {
			c.add(where("categories").is(f.category()));
		}
		if (StringUtils.hasText(f.state())) {
			// Central schemes (no state) are available in every state.
			c.add(new Criteria().orOperator(where("state").isNull(),
					where("state").regex(IndianStates.labelPattern(f.state()))));
		}
		if (StringUtils.hasText(f.level())) {
			c.add(where("level").regex(exact(f.level())));
		}
		if (StringUtils.hasText(f.beneficiaryType())) {
			c.add(where("beneficiaryTypes").regex(exact(f.beneficiaryType())));
		}
		if (StringUtils.hasText(f.gender())) {
			c.add(new Criteria().orOperator(where("eligibility.genders").exists(false),
					where("eligibility.genders").size(0), where("eligibility.genders").regex(exact(f.gender()))));
		}
		if (f.age() != null) {
			c.add(new Criteria().orOperator(where("eligibility.minAge").is(null),
					where("eligibility.minAge").lte(f.age())));
			c.add(new Criteria().orOperator(where("eligibility.maxAge").is(null),
					where("eligibility.maxAge").gte(f.age())));
		}
		if (StringUtils.hasText(f.need())) {
			c.add(Needs.fromKey(f.need()).criteria());
		}
		return c;
	}

	private static Pattern exact(String value) {
		return Pattern.compile("^" + Pattern.quote(value) + "$", Pattern.CASE_INSENSITIVE);
	}

}

package com.yojnasetu.scheme;

import static org.springframework.data.mongodb.core.query.Criteria.where;

import java.util.Arrays;
import java.util.List;
import java.util.regex.Pattern;

import org.springframework.data.mongodb.core.query.Criteria;

/**
 * "Search by user needs": each situation maps to fixed patterns over the official tags and categories of a
 * scheme. User input only selects a key; it never becomes part of a pattern.
 */
public enum Needs {

	STUDENT("student", "Student", "student|scholar|educat|school|college"),
	FARMER("farmer", "Farmer", "farm|agricult|kisan|crop|fisher|livestock"),
	SENIOR_CITIZEN("senior-citizen", "Senior citizen", "senior citizen|old age|elderly|pension"),
	SMALL_BUSINESS("small-business", "Small business owner", "business|entrepreneur|msme|self.?employ|startup"),
	WOMEN("women", "Woman", "women|woman|girl|mother|widow|maternity"),
	JOB_SEEKER("job-seeker", "Job seeker", "employment|skill|training|job|unemploy"),
	DISABILITY("disability", "Person with disability", "disab|divyang|handicap"),
	WORKER("worker", "Worker", "worker|labour|labor|construction|unorganised|artisan");

	public final String key;

	public final String label;

	private final Pattern pattern;

	Needs(String key, String label, String pattern) {
		this.key = key;
		this.label = label;
		this.pattern = Pattern.compile(pattern, Pattern.CASE_INSENSITIVE);
	}

	Criteria criteria() {
		return new Criteria().orOperator(where("tags").regex(pattern), where("categories").regex(pattern));
	}

	static Needs fromKey(String key) {
		for (Needs need : values()) {
			if (need.key.equals(key)) {
				return need;
			}
		}
		return null;
	}

	public record Option(String key, String label) {
	}

	static List<Option> options() {
		return Arrays.stream(values()).map(n -> new Option(n.key, n.label)).toList();
	}

}

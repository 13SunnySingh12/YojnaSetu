package com.yojnasetu.scheme;

import java.util.List;

/** The fields a result list needs; the full record comes from the detail endpoint. */
public record SchemeSummary(
		String id,
		String name,
		String description,
		String level,
		String state,
		String ministry,
		List<String> categories,
		List<String> tags,
		String sourceUrl,
		String sourceName) {

	static final String[] FIELDS = { "name", "description", "level", "state", "ministry", "categories", "tags",
			"sourceUrl", "sourceName" };

}

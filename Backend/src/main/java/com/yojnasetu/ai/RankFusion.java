package com.yojnasetu.ai;

import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Reciprocal rank fusion of keyword and meaning-based result lists (duplicates merge into one entry). */
final class RankFusion {

	static final int K = 60;

	record Fused(String id, double score, boolean keyword, boolean meaning) {
	}

	private RankFusion() {
	}

	static List<Fused> fuse(List<String> keyword, List<String> meaning) {
		Map<String, Double> scores = new HashMap<>();
		for (int i = 0; i < keyword.size(); i++) {
			scores.merge(keyword.get(i), 1.0 / (K + i + 1), Double::sum);
		}
		for (int i = 0; i < meaning.size(); i++) {
			scores.merge(meaning.get(i), 1.0 / (K + i + 1), Double::sum);
		}
		Set<String> byKeyword = new HashSet<>(keyword);
		Set<String> byMeaning = new HashSet<>(meaning);
		return scores.entrySet()
			.stream()
			.map(e -> new Fused(e.getKey(), e.getValue(), byKeyword.contains(e.getKey()),
					byMeaning.contains(e.getKey())))
			// A scheme found by both methods already scores highest. On a tie the meaning match wins: the
			// keyword side of a tie is often a single shared everyday word ("help", "scheme").
			.sorted(Comparator.comparingDouble(Fused::score).reversed()
				.thenComparing(f -> !f.meaning())
				.thenComparing(Fused::id))
			.toList();
	}

}

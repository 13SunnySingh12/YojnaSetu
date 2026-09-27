package com.yojnasetu.ai;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;

class RankFusionTests {

	@Test
	void resultsFoundByBothMethodsRankFirstAndDuplicatesMerge() {
		List<RankFusion.Fused> fused = RankFusion.fuse(List.of("a", "b"), List.of("c", "a"));
		assertThat(fused).extracting(RankFusion.Fused::id).containsExactly("a", "c", "b");
		assertThat(fused.get(0)).extracting(RankFusion.Fused::keyword, RankFusion.Fused::meaning)
			.containsExactly(true, true);
		assertThat(fused.get(0).score()).isEqualTo(1.0 / 61 + 1.0 / 62);
	}

	@Test
	void onEqualScoresTheMeaningMatchWins() {
		// Found live: a scheme sharing only the word "help" tied with the right scheme found by meaning.
		assertThat(RankFusion.fuse(List.of("shares-a-word"), List.of("same-meaning")))
			.extracting(RankFusion.Fused::id).containsExactly("same-meaning", "shares-a-word");
	}

	@Test
	void eitherListMayBeEmpty() {
		assertThat(RankFusion.fuse(List.of(), List.of("x"))).extracting(RankFusion.Fused::id).containsExactly("x");
		assertThat(RankFusion.fuse(List.of("y"), List.of())).extracting(RankFusion.Fused::meaning)
			.containsExactly(false);
	}

}

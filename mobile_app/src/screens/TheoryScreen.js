import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { RangeControl } from "../components/RangeControl";
import { SectionCard } from "../components/SectionCard";
import { TheoryCharts } from "../components/TheoryCharts";
import { palette } from "../theme";
import { historyLabel, posLabel, solveArea, strengthLabel } from "../utils/theory";

const sliderWords = {
  market: ["very small", "small", "mid-size", "large", "very large"],
  amenities: ["low", "some", "moderate", "high", "very high"],
  transport: ["slow", "basic", "comfortable", "fast", "very fast"]
};

export function TheoryScreen() {
  const [state, setState] = useState({
    market: 1.4,
    amenities: 0.1,
    history: 0.25,
    transport: 0.25
  });

  const solution = solveArea(state.market, state.transport, state.amenities, state.history);

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <SectionCard>
        <Text style={styles.sectionTitle}>Theoretical dashboard</Text>
        <Text style={styles.sectionBody}>
          The original site embeds a Plotly dashboard for the stylised model. Here the same reasoning is expressed through native sliders and SVG charts.
        </Text>

        <View style={styles.controls}>
          <RangeControl
            label="Market size"
            value={state.market}
            onChange={(value) => setState((current) => ({ ...current, market: value }))}
            minimumValue={0.2}
            maximumValue={1.9}
            step={0.05}
            leftLabel="small"
            rightLabel="large"
            formatValue={(value) => strengthLabel(value, 0.2, 1.9, sliderWords.market)}
          />
          <RangeControl
            label="Importance of amenities"
            value={state.amenities}
            onChange={(value) => setState((current) => ({ ...current, amenities: value }))}
            minimumValue={0.01}
            maximumValue={1}
            step={0.01}
            leftLabel="low"
            rightLabel="high"
            formatValue={(value) => strengthLabel(value, 0.01, 1, sliderWords.amenities)}
          />
          <RangeControl
            label="Historical center location"
            value={state.history}
            onChange={(value) => setState((current) => ({ ...current, history: value }))}
            minimumValue={0}
            maximumValue={1}
            step={0.01}
            leftLabel="west"
            rightLabel="east"
            formatValue={(value) => historyLabel(value)}
          />
          <RangeControl
            label="Transport factor"
            value={state.transport}
            onChange={(value) => setState((current) => ({ ...current, transport: value }))}
            minimumValue={0}
            maximumValue={1.5}
            step={0.01}
            leftLabel="slow"
            rightLabel="fast"
            formatValue={(value) => strengthLabel(value, 0, 1.5, sliderWords.transport)}
          />
        </View>
      </SectionCard>

      <TheoryCharts state={state} />

      <SectionCard>
        <Text style={styles.summaryTitle}>What this means right now</Text>
        {solution.ok ? (
          <View style={styles.summaryList}>
            <Text style={styles.summaryText}>Commercial area starts at: {posLabel(solution.q)}</Text>
            <Text style={styles.summaryText}>Commercial area ends at: {posLabel(solution.p)}</Text>
            <Text style={styles.summaryText}>Historical center: {historyLabel(solution.history)}</Text>
            <Text style={styles.summaryText}>Commercial center: {posLabel(solution.mu)}</Text>
            <Text style={styles.summaryText}>{solution.caseText}</Text>
          </View>
        ) : (
          <Text style={styles.summaryText}>{solution.reason}</Text>
        )}
      </SectionCard>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: 16,
    paddingBottom: 24
  },
  sectionTitle: {
    fontSize: 22,
    lineHeight: 26,
    color: palette.ink,
    fontFamily: "Georgia",
    fontWeight: "700"
  },
  sectionBody: {
    marginTop: 10,
    fontSize: 14,
    lineHeight: 20,
    color: palette.muted
  },
  controls: {
    gap: 14,
    marginTop: 16
  },
  summaryTitle: {
    fontSize: 18,
    color: palette.ink,
    fontWeight: "800",
    marginBottom: 12
  },
  summaryList: {
    gap: 8
  },
  summaryText: {
    fontSize: 14,
    lineHeight: 20,
    color: palette.ink
  }
});

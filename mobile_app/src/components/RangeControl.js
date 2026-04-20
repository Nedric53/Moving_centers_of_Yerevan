import React from "react";
import { StyleSheet, Text, View } from "react-native";
import Slider from "@react-native-community/slider";

import { palette } from "../theme";

export function RangeControl({
  label,
  value,
  onChange,
  minimumValue,
  maximumValue,
  step,
  leftLabel,
  rightLabel,
  formatValue
}) {
  return (
    <View style={styles.block}>
      <View style={styles.topRow}>
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.value}>{formatValue ? formatValue(value) : value.toFixed(2)}</Text>
      </View>
      <Slider
        value={value}
        onValueChange={onChange}
        minimumValue={minimumValue}
        maximumValue={maximumValue}
        step={step}
        minimumTrackTintColor={palette.cyan}
        maximumTrackTintColor={palette.sand}
        thumbTintColor={palette.accent}
      />
      <View style={styles.ends}>
        <Text style={styles.endLabel}>{leftLabel}</Text>
        <Text style={styles.endLabel}>{rightLabel}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  block: {
    gap: 4
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12
  },
  label: {
    flex: 1,
    fontSize: 15,
    color: palette.ink,
    fontWeight: "700"
  },
  value: {
    fontSize: 13,
    color: palette.muted,
    fontWeight: "700"
  },
  ends: {
    flexDirection: "row",
    justifyContent: "space-between"
  },
  endLabel: {
    fontSize: 12,
    color: palette.muted
  }
});

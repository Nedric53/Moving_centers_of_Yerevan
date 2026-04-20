import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Line, Path } from "react-native-svg";

import { palette, radius } from "../theme";
import { convertYerevanGeomToMeters, projectMetersToPath } from "../utils/geo";

export function ComparisonCanvas({ cityGeom, yerevanGeom, origin, extent }) {
  const [size, setSize] = useState({ width: 320, height: 320 });

  function onLayout(event) {
    const { width } = event.nativeEvent.layout;
    setSize({ width: Math.max(10, width), height: 320 });
  }

  const range = Math.max(500, extent || 500);
  const yerevanMeters = convertYerevanGeomToMeters(yerevanGeom, origin);
  const cityPath = projectMetersToPath(cityGeom, size.width, size.height, range);
  const yerevanPath = projectMetersToPath(yerevanMeters, size.width, size.height, range);
  const centerX = size.width / 2;
  const centerY = size.height / 2;

  return (
    <View style={styles.wrapper}>
      <View style={styles.frame} onLayout={onLayout}>
        <Svg width={size.width} height={size.height}>
          <Line x1="0" y1={centerY} x2={size.width} y2={centerY} stroke={palette.line} strokeWidth="1" />
          <Line x1={centerX} y1="0" x2={centerX} y2={size.height} stroke={palette.line} strokeWidth="1" />
          <Path d={cityPath} fill="rgba(240,128,91,0.18)" stroke={palette.accent} strokeWidth="2" fillRule="evenodd" />
          <Path d={yerevanPath} fill="rgba(0,155,190,0.18)" stroke="rgba(0,155,190,0.95)" strokeWidth="2" fillRule="evenodd" />
          <Circle cx={centerX} cy={centerY} r="6" fill="rgba(220,60,60,0.95)" />
        </Svg>
        <Text style={[styles.axisLabel, styles.topLabel]}>up</Text>
        <Text style={[styles.axisLabel, styles.bottomLabel]}>down</Text>
        <Text style={[styles.axisLabel, styles.leftLabel]}>left</Text>
        <Text style={[styles.axisLabel, styles.rightLabel]}>right</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    gap: 10
  },
  frame: {
    height: 320,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: palette.line,
    backgroundColor: "#ffffff",
    overflow: "hidden",
    position: "relative"
  },
  axisLabel: {
    position: "absolute",
    fontSize: 12,
    color: palette.muted
  },
  topLabel: {
    top: 10,
    left: "50%",
    transform: [{ translateX: -10 }]
  },
  bottomLabel: {
    bottom: 10,
    left: "50%",
    transform: [{ translateX: -16 }]
  },
  leftLabel: {
    left: 10,
    top: "50%",
    transform: [{ translateY: -8 }]
  },
  rightLabel: {
    right: 10,
    top: "50%",
    transform: [{ translateY: -8 }]
  }
});

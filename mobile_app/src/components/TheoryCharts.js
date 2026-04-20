import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Line, Path } from "react-native-svg";

import { palette, radius } from "../theme";
import { scanHistory, scanTransport, solveArea } from "../utils/theory";

function ChartFrame({ title, subtitle, children, height = 240 }) {
  return (
    <View style={styles.chartCard}>
      <Text style={styles.chartTitle}>{title}</Text>
      <Text style={styles.chartSubtitle}>{subtitle}</Text>
      <View style={[styles.chartFrame, { height }]}>{children}</View>
    </View>
  );
}

function useChartSize(defaultHeight) {
  const [size, setSize] = useState({ width: 320, height: defaultHeight });
  function onLayout(event) {
    const { width } = event.nativeEvent.layout;
    setSize({ width: Math.max(20, width), height: defaultHeight });
  }
  return [size, onLayout];
}

function pathFromSeries(points, xDomain, yDomain, width, height) {
  const valid = points.filter((point) => point.y !== null && Number.isFinite(point.y));
  if (!valid.length) return "";

  const project = (x, y) => {
    const px = ((x - xDomain[0]) / (xDomain[1] - xDomain[0])) * width;
    const py = height - ((y - yDomain[0]) / (yDomain[1] - yDomain[0])) * height;
    return [px, py];
  };

  let path = "";
  valid.forEach((point, index) => {
    const [px, py] = project(point.x, point.y);
    path += `${index === 0 ? "M" : "L"} ${px.toFixed(2)} ${py.toFixed(2)} `;
  });

  return path.trim();
}

function LayoutChart({ solution }) {
  const [size, onLayout] = useChartSize(170);
  const width = size.width;
  const height = size.height;
  const projectX = (value) => ((value + 1) / 2) * width;
  const centerY = height / 2;

  return (
    <View onLayout={onLayout} style={styles.fill}>
      <Svg width={width} height={height}>
        <Line x1="0" y1={centerY} x2={width} y2={centerY} stroke={palette.line} strokeWidth="1" />
        {solution.ok ? (
          <>
            <Line
              x1={projectX(solution.q)}
              y1={centerY}
              x2={projectX(solution.p)}
              y2={centerY}
              stroke={palette.accent}
              strokeWidth="12"
              strokeLinecap="round"
            />
            <Circle cx={projectX(solution.mu)} cy={centerY} r="6" fill={palette.cyan} />
            <Line
              x1={projectX(solution.history) - 6}
              y1={centerY - 6}
              x2={projectX(solution.history) + 6}
              y2={centerY + 6}
              stroke="#DC3C3C"
              strokeWidth="2"
            />
            <Line
              x1={projectX(solution.history) - 6}
              y1={centerY + 6}
              x2={projectX(solution.history) + 6}
              y2={centerY - 6}
              stroke="#DC3C3C"
              strokeWidth="2"
            />
          </>
        ) : null}
      </Svg>
    </View>
  );
}

function HistoryChart({ state }) {
  const [size, onLayout] = useChartSize(220);
  const { histories, starts, ends } = scanHistory(state);
  const startPath = pathFromSeries(
    histories.map((x, index) => ({ x, y: starts[index] })),
    [0, 1],
    [-1, 1],
    size.width,
    size.height
  );
  const endPath = pathFromSeries(
    histories.map((x, index) => ({ x, y: ends[index] })),
    [0, 1],
    [-1, 1],
    size.width,
    size.height
  );

  const current = solveArea(state.market, state.transport, state.amenities, state.history);
  const currentX = size.width * state.history;
  const currentStartY = current.ok ? size.height - ((current.q + 1) / 2) * size.height : null;
  const currentEndY = current.ok ? size.height - ((current.p + 1) / 2) * size.height : null;

  return (
    <View onLayout={onLayout} style={styles.fill}>
      <Svg width={size.width} height={size.height}>
        <Line x1="0" y1={size.height / 2} x2={size.width} y2={size.height / 2} stroke={palette.line} strokeWidth="1" />
        <Path d={startPath} stroke={palette.cyan} strokeWidth="3" fill="none" />
        <Path d={endPath} stroke={palette.accent} strokeWidth="3" fill="none" />
        <Line x1={currentX} y1="0" x2={currentX} y2={size.height} stroke={palette.line} strokeWidth="2" strokeDasharray="5 5" />
        {current.ok ? (
          <>
            <Circle cx={currentX} cy={currentStartY} r="4" fill={palette.cyan} />
            <Circle cx={currentX} cy={currentEndY} r="4" fill={palette.accent} />
          </>
        ) : null}
      </Svg>
    </View>
  );
}

function TransportChart({ state }) {
  const [size, onLayout] = useChartSize(220);
  const { transports, starts, ends } = scanTransport(state);
  const startPath = pathFromSeries(
    transports.map((y, index) => ({ x: starts[index], y })),
    [-1, 1],
    [0, 1.5],
    size.width,
    size.height
  );
  const endPath = pathFromSeries(
    transports.map((y, index) => ({ x: ends[index], y })),
    [-1, 1],
    [0, 1.5],
    size.width,
    size.height
  );

  const current = solveArea(state.market, state.transport, state.amenities, state.history);
  const currentY = size.height - (state.transport / 1.5) * size.height;
  const currentStartX = current.ok ? ((current.q + 1) / 2) * size.width : null;
  const currentEndX = current.ok ? ((current.p + 1) / 2) * size.width : null;
  const historyX = ((state.history + 1) / 2) * size.width;

  return (
    <View onLayout={onLayout} style={styles.fill}>
      <Svg width={size.width} height={size.height}>
        <Line x1={historyX} y1="0" x2={historyX} y2={size.height} stroke={palette.line} strokeWidth="2" strokeDasharray="5 5" />
        <Path d={startPath} stroke={palette.cyan} strokeWidth="3" fill="none" />
        <Path d={endPath} stroke={palette.accent} strokeWidth="3" fill="none" />
        {current.ok ? (
          <>
            <Circle cx={currentStartX} cy={currentY} r="4" fill={palette.cyan} />
            <Circle cx={currentEndX} cy={currentY} r="4" fill={palette.accent} />
          </>
        ) : null}
      </Svg>
    </View>
  );
}

export function TheoryCharts({ state }) {
  const solution = solveArea(state.market, state.transport, state.amenities, state.history);

  return (
    <View style={styles.container}>
      <ChartFrame
        title="Commercial layout"
        subtitle="The thick segment is the commercial area. The red X is the historical center and the cyan point is the commercial center."
        height={170}
      >
        <LayoutChart solution={solution} />
      </ChartFrame>

      <ChartFrame
        title="Historical center scan"
        subtitle="How the area edges move when the historical center shifts from west to east."
      >
        <HistoryChart state={state} />
      </ChartFrame>

      <ChartFrame
        title="Transport scan"
        subtitle="How the area edges react as transport conditions improve."
      >
        <TransportChart state={state} />
      </ChartFrame>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 16
  },
  chartCard: {
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: palette.line,
    backgroundColor: "#ffffff",
    padding: 14,
    gap: 6
  },
  chartTitle: {
    fontSize: 15,
    color: palette.ink,
    fontWeight: "800"
  },
  chartSubtitle: {
    fontSize: 12,
    lineHeight: 17,
    color: palette.muted
  },
  chartFrame: {
    overflow: "hidden"
  },
  fill: {
    flex: 1
  }
});

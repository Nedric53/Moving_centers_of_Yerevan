import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, View, Pressable } from "react-native";
import MapView, { Marker, Polygon } from "react-native-maps";

import { SectionCard } from "../components/SectionCard";
import { RangeControl } from "../components/RangeControl";
import { palette, radius } from "../theme";
import { buildScenarioKey, computeRegionFromGeometry, geoJsonToMapPolygons } from "../utils/geo";

const precomputed = require("../data/yerevan-precomputed.json");
const boundary = require("../data/yerevan-boundary.json");

const scenarios = [
  { label: "Baseline", t: 1.0, a: 1.0 },
  { label: "Slower transport", t: 1.25, a: 1.0 },
  { label: "Faster transport", t: 0.75, a: 1.0 },
  { label: "Historic pull", t: 1.0, a: 1.25 },
  { label: "Weaker amenities", t: 1.0, a: 0.75 }
];

const mapRegion = computeRegionFromGeometry(boundary.geometry, 1.1);
const boundaryPolygons = geoJsonToMapPolygons(boundary.geometry);

export function YerevanScreen() {
  const [transport, setTransport] = useState(1.0);
  const [amenity, setAmenity] = useState(1.0);

  const entry = precomputed.precomp[buildScenarioKey(transport, amenity)];
  const businessPolygons = entry?.poly_geom ? geoJsonToMapPolygons(entry.poly_geom) : [];

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <SectionCard>
        <Text style={styles.sectionTitle}>Yerevan commercial area</Text>
        <Text style={styles.sectionBody}>
          This native screen uses the same precomputed scenarios as the original project and renders them on a real mobile map instead of inside an HTML iframe.
        </Text>

        <View style={styles.scenarioRow}>
          {scenarios.map((scenario) => {
            const active = scenario.t === transport && scenario.a === amenity;
            return (
              <Pressable
                key={scenario.label}
                onPress={() => {
                  setTransport(scenario.t);
                  setAmenity(scenario.a);
                }}
                style={[styles.scenarioChip, active && styles.scenarioChipActive]}
              >
                <Text style={[styles.scenarioLabel, active && styles.scenarioLabelActive]}>{scenario.label}</Text>
              </Pressable>
            );
          })}
        </View>

        <View style={styles.controls}>
          <RangeControl
            label="Transport factor"
            value={transport}
            onChange={setTransport}
            minimumValue={precomputed.t_grid.min}
            maximumValue={precomputed.t_grid.max}
            step={precomputed.t_grid.step}
            leftLabel="slower"
            rightLabel="faster"
            formatValue={(value) => value.toFixed(2)}
          />

          <RangeControl
            label="Historic amenity strength"
            value={amenity}
            onChange={setAmenity}
            minimumValue={precomputed.a_grid.min}
            maximumValue={precomputed.a_grid.max}
            step={precomputed.a_grid.step}
            leftLabel="weaker"
            rightLabel="stronger"
            formatValue={(value) => value.toFixed(2)}
          />
        </View>
      </SectionCard>

      <SectionCard style={styles.mapCard}>
        <MapView style={styles.map} initialRegion={mapRegion}>
          {boundaryPolygons.map((polygon, index) => (
            <Polygon
              key={`boundary-${index}`}
              coordinates={polygon.coordinates}
              holes={polygon.holes}
              strokeColor="rgba(45,38,31,0.5)"
              fillColor="rgba(45,38,31,0.02)"
              strokeWidth={1.5}
            />
          ))}

          {businessPolygons.map((polygon, index) => (
            <Polygon
              key={`business-${index}`}
              coordinates={polygon.coordinates}
              holes={polygon.holes}
              strokeColor="rgba(240,128,91,0.95)"
              fillColor="rgba(87,212,229,0.18)"
              strokeWidth={2}
            />
          ))}

          <Marker coordinate={{ latitude: precomputed.g.lat, longitude: precomputed.g.lon }}>
            <View style={[styles.marker, styles.historyMarker]} />
          </Marker>

          {entry?.mu ? (
            <Marker coordinate={{ latitude: entry.mu.lat, longitude: entry.mu.lon }}>
              <View style={[styles.marker, styles.businessMarker]} />
            </Marker>
          ) : null}
        </MapView>

        <View style={styles.legendRow}>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, styles.historyMarker]} />
            <Text style={styles.legendText}>Historical center</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, styles.businessMarker]} />
            <Text style={styles.legendText}>Commercial center</Text>
          </View>
        </View>
      </SectionCard>

      <SectionCard>
        <Text style={styles.metricTitle}>Current scenario</Text>
        <View style={styles.metricGrid}>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{entry ? entry.area_km2.toFixed(2) : "--"} km²</Text>
            <Text style={styles.metricLabel}>Commercial area</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{entry ? entry.sep_m.toFixed(0) : "--"} m</Text>
            <Text style={styles.metricLabel}>Distance to historical center</Text>
          </View>
        </View>
        <Text style={styles.note}>
          The polygon and commercial center update natively as you move the sliders, using the same scenario table the site already generated.
        </Text>
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
  scenarioRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 14
  },
  scenarioChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.line,
    backgroundColor: "#ffffff",
    paddingHorizontal: 12,
    paddingVertical: 8
  },
  scenarioChipActive: {
    backgroundColor: palette.cyanSoft,
    borderColor: palette.cyan
  },
  scenarioLabel: {
    fontSize: 12,
    color: palette.ink,
    fontWeight: "700"
  },
  scenarioLabelActive: {
    color: "#116a74"
  },
  controls: {
    gap: 14,
    marginTop: 16
  },
  mapCard: {
    padding: 10
  },
  map: {
    width: "100%",
    height: 360,
    borderRadius: radius.md
  },
  marker: {
    width: 18,
    height: 18,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: "#ffffff"
  },
  historyMarker: {
    backgroundColor: "#DC3C3C"
  },
  businessMarker: {
    backgroundColor: palette.accent
  },
  legendRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 14,
    paddingHorizontal: 8,
    paddingTop: 12
  },
  legendItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  legendDot: {
    width: 12,
    height: 12,
    borderRadius: 999
  },
  legendText: {
    fontSize: 12,
    color: palette.muted
  },
  metricTitle: {
    fontSize: 18,
    color: palette.ink,
    fontWeight: "800",
    marginBottom: 12
  },
  metricGrid: {
    flexDirection: "row",
    gap: 12
  },
  metricCard: {
    flex: 1,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: palette.line,
    backgroundColor: "#fffaf4",
    padding: 14,
    gap: 6
  },
  metricValue: {
    fontSize: 22,
    color: palette.ink,
    fontWeight: "800"
  },
  metricLabel: {
    fontSize: 12,
    lineHeight: 16,
    color: palette.muted
  },
  note: {
    marginTop: 14,
    fontSize: 13,
    lineHeight: 19,
    color: palette.muted
  }
});

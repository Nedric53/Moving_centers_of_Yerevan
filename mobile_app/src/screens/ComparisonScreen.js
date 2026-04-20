import React, { useState } from "react";
import { FlatList, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { ComparisonCanvas } from "../components/ComparisonCanvas";
import { RangeControl } from "../components/RangeControl";
import { SectionCard } from "../components/SectionCard";
import { palette, radius } from "../theme";
import { buildScenarioKey } from "../utils/geo";

const cityComparison = require("../data/city-comparison.json");
const precomputed = require("../data/yerevan-precomputed.json");

const cityNames = Object.keys(cityComparison.cities).sort((left, right) => left.localeCompare(right));
const defaultCity = cityNames.includes("Tbilisi, Georgia") ? "Tbilisi, Georgia" : cityNames[0];

export function ComparisonScreen() {
  const [transport, setTransport] = useState(1.0);
  const [amenity, setAmenity] = useState(1.0);
  const [cityName, setCityName] = useState(defaultCity);
  const [pickerOpen, setPickerOpen] = useState(false);

  const entry = precomputed.precomp[buildScenarioKey(transport, amenity)];
  const city = cityComparison.cities[cityName];

  return (
    <>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <SectionCard>
          <Text style={styles.sectionTitle}>Commercial areas comparison</Text>
          <Text style={styles.sectionBody}>
            Compare Yerevan’s dynamic commercial area with another city on the same meters-based canvas centered on each historical core.
          </Text>

          <Pressable style={styles.cityButton} onPress={() => setPickerOpen(true)}>
            <Text style={styles.cityButtonLabel}>Comparison city</Text>
            <Text style={styles.cityButtonValue}>{cityName}</Text>
          </Pressable>

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

        <SectionCard>
          <View style={styles.legendRow}>
            <View style={styles.legendItem}>
              <View style={[styles.swatch, { backgroundColor: "rgba(0,155,190,0.18)", borderColor: "rgba(0,155,190,0.95)" }]} />
              <Text style={styles.legendText}>Yerevan commercial area</Text>
            </View>
            <View style={styles.legendItem}>
              <View style={[styles.swatch, { backgroundColor: "rgba(240,128,91,0.18)", borderColor: palette.accent }]} />
              <Text style={styles.legendText}>{cityName} commercial area</Text>
            </View>
            <View style={styles.legendItem}>
              <View style={[styles.dot, { backgroundColor: "#DC3C3C" }]} />
              <Text style={styles.legendText}>Historical center</Text>
            </View>
          </View>

          <ComparisonCanvas
            cityGeom={city?.geom_m}
            yerevanGeom={entry?.poly_geom}
            origin={precomputed.g}
            extent={cityComparison.extent_m}
          />
        </SectionCard>

        <SectionCard>
          <View style={styles.metricGrid}>
            <View style={styles.metricCard}>
              <Text style={styles.metricCaption}>Yerevan</Text>
              <Text style={styles.metricValue}>{entry ? entry.area_km2.toFixed(2) : "--"} km²</Text>
              <Text style={styles.metricNote}>
                {entry ? `${entry.sep_m.toFixed(0)} m from commercial center to historical center` : "No scenario data"}
              </Text>
            </View>
            <View style={styles.metricCard}>
              <Text style={styles.metricCaption}>{cityName}</Text>
              <Text style={styles.metricValue}>{city ? city.area_km2.toFixed(2) : "--"} km²</Text>
              <Text style={styles.metricNote}>Static business area from the comparison dataset</Text>
            </View>
          </View>
        </SectionCard>
      </ScrollView>

      <Modal animationType="slide" visible={pickerOpen} transparent onRequestClose={() => setPickerOpen(false)}>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Choose a city</Text>
            <FlatList
              data={cityNames}
              keyExtractor={(item) => item}
              renderItem={({ item }) => {
                const active = item === cityName;
                return (
                  <Pressable
                    onPress={() => {
                      setCityName(item);
                      setPickerOpen(false);
                    }}
                    style={[styles.cityRow, active && styles.cityRowActive]}
                  >
                    <Text style={[styles.cityRowText, active && styles.cityRowTextActive]}>{item}</Text>
                  </Pressable>
                );
              }}
            />
            <Pressable onPress={() => setPickerOpen(false)} style={styles.closeButton}>
              <Text style={styles.closeButtonText}>Close</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </>
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
  cityButton: {
    marginTop: 16,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: palette.line,
    backgroundColor: "#fffaf4",
    padding: 14,
    gap: 4
  },
  cityButtonLabel: {
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    color: palette.muted,
    fontWeight: "700"
  },
  cityButtonValue: {
    fontSize: 18,
    color: palette.ink,
    fontWeight: "800"
  },
  controls: {
    gap: 14,
    marginTop: 16
  },
  legendRow: {
    gap: 10,
    marginBottom: 12
  },
  legendItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  swatch: {
    width: 14,
    height: 10,
    borderRadius: 3,
    borderWidth: 1
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 999
  },
  legendText: {
    fontSize: 12,
    color: palette.muted
  },
  metricGrid: {
    gap: 12
  },
  metricCard: {
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: palette.line,
    backgroundColor: "#ffffff",
    padding: 14,
    gap: 6
  },
  metricCaption: {
    fontSize: 13,
    color: palette.muted,
    fontWeight: "700"
  },
  metricValue: {
    fontSize: 24,
    color: palette.ink,
    fontWeight: "800"
  },
  metricNote: {
    fontSize: 12,
    lineHeight: 17,
    color: palette.muted
  },
  modalBackdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.32)"
  },
  modalSheet: {
    maxHeight: "78%",
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    backgroundColor: palette.surface,
    padding: 18
  },
  modalTitle: {
    fontSize: 20,
    color: palette.ink,
    fontFamily: "Georgia",
    fontWeight: "700",
    marginBottom: 12
  },
  cityRow: {
    borderRadius: radius.sm,
    paddingHorizontal: 12,
    paddingVertical: 12
  },
  cityRowActive: {
    backgroundColor: palette.cyanSoft
  },
  cityRowText: {
    fontSize: 14,
    color: palette.ink
  },
  cityRowTextActive: {
    fontWeight: "800"
  },
  closeButton: {
    marginTop: 12,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 999,
    backgroundColor: palette.accent,
    paddingVertical: 12
  },
  closeButtonText: {
    fontSize: 14,
    color: "#ffffff",
    fontWeight: "800"
  }
});

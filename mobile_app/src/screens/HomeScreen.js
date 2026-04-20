import React from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { SectionCard } from "../components/SectionCard";
import { palette, radius } from "../theme";

const heroImage = require("../../assets/images/hero_cover.png");
const centersMap = require("../../assets/images/city_centers_map.png");

const features = [
  {
    key: "yerevan",
    title: "Yerevan model",
    body: "Interactive transport and amenity sliders on a real mobile map."
  },
  {
    key: "compare",
    title: "City comparison",
    body: "Compare Yerevan with other business areas in a shared meters scale."
  },
  {
    key: "theory",
    title: "Theory dashboard",
    body: "Native charts for the analytical model behind the site."
  }
];

export function HomeScreen({ onNavigate }) {
  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <SectionCard style={styles.heroCard}>
        <View style={styles.heroCopy}>
          <Text style={styles.heroTitle}>How and why the commercial centers of cities move away from historical centers.</Text>
          <Text style={styles.heroBody}>
            This mobile version keeps the same project logic as the site, but rebuilds the experience as a native client with mobile-first navigation, sliders, charts and map interactions.
          </Text>
        </View>
        <Image source={heroImage} style={styles.heroImage} resizeMode="cover" />
      </SectionCard>

      <View style={styles.featureList}>
        {features.map((feature) => (
          <Pressable key={feature.key} onPress={() => onNavigate(feature.key)}>
            <SectionCard style={styles.featureCard}>
              <Text style={styles.featureTitle}>{feature.title}</Text>
              <Text style={styles.featureBody}>{feature.body}</Text>
              <Text style={styles.featureLink}>Open</Text>
            </SectionCard>
          </Pressable>
        ))}
      </View>

      <SectionCard>
        <Text style={styles.sectionTitle}>What centers does a city have?</Text>
        <Image source={centersMap} style={styles.mapImage} resizeMode="cover" />
        <View style={styles.copyGroup}>
          <Text style={styles.bodyText}>
            <Text style={styles.bodyStrong}>Historical center</Text> is the historically formed part of the city where the original layout and heritage buildings are concentrated.
          </Text>
          <Text style={styles.bodyText}>
            <Text style={styles.bodyStrong}>Commercial center</Text> is a conceptual point representing where business activity is concentrated through jobs, offices, retail and transport hubs.
          </Text>
          <Text style={styles.bodyText}>
            In Yerevan, Republic Square is treated as the historical center, while the commercial center lies roughly 1.1 km away near the City Council area.
          </Text>
        </View>
      </SectionCard>

      <SectionCard>
        <Text style={styles.sectionTitle}>Why they separate</Text>
        <Text style={styles.bodyText}>
          The site points to two major drivers: transport conditions across the city and the amenity value of the historical fabric. As transport improves and accessibility patterns change, business activity can drift away from the older core.
        </Text>
        <Text style={styles.bodyText}>
          The screens in this app let you test those shifts directly and compare Yerevan with business areas in other cities.
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
  heroCard: {
    gap: 16,
    overflow: "hidden",
    backgroundColor: "#fffaf4"
  },
  heroCopy: {
    gap: 10
  },
  heroTitle: {
    fontSize: 28,
    lineHeight: 34,
    color: palette.accent,
    fontFamily: "Georgia",
    fontWeight: "700"
  },
  heroBody: {
    fontSize: 15,
    lineHeight: 22,
    color: palette.ink
  },
  heroImage: {
    width: "100%",
    height: 220,
    borderRadius: radius.md
  },
  featureList: {
    gap: 12
  },
  featureCard: {
    gap: 8
  },
  featureTitle: {
    fontSize: 18,
    color: palette.ink,
    fontWeight: "800"
  },
  featureBody: {
    fontSize: 14,
    lineHeight: 20,
    color: palette.muted
  },
  featureLink: {
    fontSize: 13,
    color: palette.accent,
    fontWeight: "800"
  },
  sectionTitle: {
    fontSize: 22,
    lineHeight: 26,
    color: palette.ink,
    fontFamily: "Georgia",
    fontWeight: "700",
    marginBottom: 12
  },
  mapImage: {
    width: "100%",
    height: 240,
    borderRadius: radius.md,
    marginBottom: 14
  },
  copyGroup: {
    gap: 10
  },
  bodyText: {
    fontSize: 14,
    lineHeight: 21,
    color: palette.ink
  },
  bodyStrong: {
    fontWeight: "800"
  }
});

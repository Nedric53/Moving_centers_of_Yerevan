import React, { useState } from "react";
import { SafeAreaView, ScrollView, StyleSheet, Text, View, Pressable } from "react-native";
import { StatusBar } from "expo-status-bar";

import { HomeScreen } from "./src/screens/HomeScreen";
import { YerevanScreen } from "./src/screens/YerevanScreen";
import { ComparisonScreen } from "./src/screens/ComparisonScreen";
import { TheoryScreen } from "./src/screens/TheoryScreen";
import { palette } from "./src/theme";

const tabs = [
  { key: "home", label: "Home" },
  { key: "yerevan", label: "Yerevan" },
  { key: "compare", label: "Compare" },
  { key: "theory", label: "Theory" }
];

export default function App() {
  const [activeTab, setActiveTab] = useState("home");

  let content = null;
  if (activeTab === "home") {
    content = <HomeScreen onNavigate={setActiveTab} />;
  } else if (activeTab === "yerevan") {
    content = <YerevanScreen />;
  } else if (activeTab === "compare") {
    content = <ComparisonScreen />;
  } else {
    content = <TheoryScreen />;
  }

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      <View style={styles.backgroundBlobTop} />
      <View style={styles.backgroundBlobBottom} />
      <View style={styles.shell}>
        <View style={styles.header}>
          <View>
            <Text style={styles.kicker}>Native mobile app</Text>
            <Text style={styles.title}>Moving Centers of Yerevan</Text>
          </View>
          <Text style={styles.subtitle}>Same analytical core, rebuilt as a mobile client.</Text>
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.tabRow}
          style={styles.tabScroller}
        >
          {tabs.map((tab) => {
            const isActive = activeTab === tab.key;
            return (
              <Pressable
                key={tab.key}
                onPress={() => setActiveTab(tab.key)}
                style={[styles.tabButton, isActive && styles.tabButtonActive]}
              >
                <Text style={[styles.tabLabel, isActive && styles.tabLabelActive]}>{tab.label}</Text>
              </Pressable>
            );
          })}
        </ScrollView>

        <View style={styles.content}>{content}</View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: palette.background
  },
  shell: {
    flex: 1,
    paddingHorizontal: 18,
    paddingBottom: 16
  },
  backgroundBlobTop: {
    position: "absolute",
    top: -60,
    right: -30,
    width: 220,
    height: 220,
    borderRadius: 999,
    backgroundColor: "rgba(240,128,91,0.18)"
  },
  backgroundBlobBottom: {
    position: "absolute",
    bottom: -40,
    left: -60,
    width: 260,
    height: 260,
    borderRadius: 999,
    backgroundColor: "rgba(87,212,229,0.16)"
  },
  header: {
    gap: 4,
    paddingTop: 6,
    paddingBottom: 14
  },
  kicker: {
    fontSize: 12,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    color: palette.muted,
    fontWeight: "700"
  },
  title: {
    fontSize: 30,
    lineHeight: 34,
    color: palette.ink,
    fontFamily: "Georgia",
    fontWeight: "700"
  },
  subtitle: {
    fontSize: 14,
    lineHeight: 20,
    color: palette.muted
  },
  tabScroller: {
    flexGrow: 0
  },
  tabRow: {
    gap: 10,
    paddingBottom: 14
  },
  tabButton: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.line,
    backgroundColor: palette.surface
  },
  tabButtonActive: {
    backgroundColor: palette.accent,
    borderColor: palette.accent
  },
  tabLabel: {
    fontSize: 14,
    color: palette.ink,
    fontWeight: "700"
  },
  tabLabelActive: {
    color: "#ffffff"
  },
  content: {
    flex: 1
  }
});

import { useCallback, useEffect, useRef, useState } from "react";
import { BackHandler, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as Linking from "expo-linking";
import * as SplashScreen from "expo-splash-screen";
import * as WebBrowser from "expo-web-browser";
import NetInfo from "@react-native-community/netinfo";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { WebView, type WebViewNavigation } from "react-native-webview";
import type { ShouldStartLoadRequest } from "react-native-webview/lib/WebViewTypes";
import { classifyNavigation, deepLinkToSiteUrl, SITE_ORIGIN } from "./src/navigation";
import { copyFor } from "./src/copy";

SplashScreen.preventAutoHideAsync().catch(() => {});

// Matches the site's dark brand background (apps/web/app/icon.svg).
const BACKGROUND = "#090B0E";
const FOREGROUND = "#E6E3E1";
const copy = copyFor(Intl.DateTimeFormat().resolvedOptions().locale);

type Failure = "offline" | "unreachable" | null;

function openOutside(url: string) {
  const target = classifyNavigation(url);
  if (target === "browser") {
    WebBrowser.openBrowserAsync(url, { controlsColor: FOREGROUND, toolbarColor: BACKGROUND }).catch(() =>
      Linking.openURL(url).catch(() => {}),
    );
  } else if (target === "system") {
    Linking.openURL(url).catch(() => {});
  }
}

function Shell() {
  const webView = useRef<WebView>(null);
  const canGoBack = useRef(false);
  const linkingUrl = Linking.useLinkingURL();
  const [source, setSource] = useState(() => ({ uri: deepLinkToSiteUrl(linkingUrl) ?? `${SITE_ORIGIN}/` }));
  const [failure, setFailure] = useState<Failure>(null);
  const [connected, setConnected] = useState(true);

  const hideSplash = useCallback(() => {
    SplashScreen.hideAsync().catch(() => {});
  }, []);

  // A link that opens the app, at launch or later, navigates the existing session.
  useEffect(() => {
    const target = deepLinkToSiteUrl(linkingUrl);
    if (target) setSource((current) => (current.uri === target ? current : { uri: target }));
  }, [linkingUrl]);

  useEffect(
    () =>
      NetInfo.addEventListener((state) => {
        setConnected(state.isConnected !== false);
      }),
    [],
  );

  useEffect(() => {
    if (Platform.OS !== "android") return;
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => {
      if (!canGoBack.current) return false;
      webView.current?.goBack();
      return true;
    });
    return () => subscription.remove();
  }, []);

  const onShouldStartLoadWithRequest = useCallback((request: ShouldStartLoadRequest) => {
    // Sub-frames (embedded evidence, maps) load as the page intends.
    if (request.isTopFrame === false) return true;
    if (classifyNavigation(request.url) === "app") return true;
    openOutside(request.url);
    return false;
  }, []);

  const onNavigationStateChange = useCallback((state: WebViewNavigation) => {
    canGoBack.current = state.canGoBack;
  }, []);

  const retry = useCallback(() => {
    setFailure(null);
    webView.current?.reload();
  }, []);

  const showFailure: Failure = failure ?? (connected ? null : "offline");

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom", "left", "right"]}>
      <StatusBar style="light" />
      <WebView
        ref={webView}
        source={source}
        style={styles.webView}
        originWhitelist={["https://*", "http://*", "about:*", "blob:*", "data:*", "mailto:*", "tel:*", "sms:*"]}
        applicationNameForUserAgent="HelveticLensApp/1.0"
        sharedCookiesEnabled
        thirdPartyCookiesEnabled={false}
        domStorageEnabled
        javaScriptEnabled
        allowsBackForwardNavigationGestures
        pullToRefreshEnabled
        allowsInlineMediaPlayback
        setSupportMultipleWindows={false}
        allowFileAccess={false}
        allowsLinkPreview={false}
        onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
        onOpenWindow={({ nativeEvent }) => openOutside(nativeEvent.targetUrl)}
        onNavigationStateChange={onNavigationStateChange}
        onLoadEnd={hideSplash}
        onLoad={() => setFailure(null)}
        onError={() => {
          setFailure(connected ? "unreachable" : "offline");
          hideSplash();
        }}
        onHttpError={({ nativeEvent }) => {
          // Only a failing gateway means the site is down; app errors render their own page.
          if (nativeEvent.statusCode >= 502 && nativeEvent.statusCode <= 504) setFailure("unreachable");
        }}
        onContentProcessDidTerminate={() => webView.current?.reload()}
        onRenderProcessGone={() => webView.current?.reload()}
      />
      {showFailure ? (
        <View style={styles.failure} accessibilityLiveRegion="polite">
          <Text style={styles.title} accessibilityRole="header">
            {showFailure === "offline" ? copy.offlineTitle : copy.errorTitle}
          </Text>
          <Text style={styles.body}>{showFailure === "offline" ? copy.offlineBody : copy.errorBody}</Text>
          <Pressable accessibilityRole="button" onPress={retry} style={styles.button}>
            <Text style={styles.buttonText}>{copy.retry}</Text>
          </Pressable>
        </View>
      ) : null}
    </SafeAreaView>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <Shell />
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: BACKGROUND },
  webView: { flex: 1, backgroundColor: BACKGROUND },
  failure: {
    ...StyleSheet.absoluteFill,
    backgroundColor: BACKGROUND,
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
    gap: 16,
  },
  title: { color: FOREGROUND, fontSize: 22, fontWeight: "600", textAlign: "center" },
  body: { color: FOREGROUND, opacity: 0.8, fontSize: 16, lineHeight: 22, textAlign: "center" },
  button: {
    marginTop: 8,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: FOREGROUND,
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  buttonText: { color: FOREGROUND, fontSize: 16, fontWeight: "600" },
});

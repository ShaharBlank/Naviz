import * as Localization from "expo-localization";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { I18nManager } from "react-native";

const resources = {
  he: {
    translation: {
      appName: "Naviz",
      tagline: "ניווט חכם יותר לעיר",
      searchPlaceholder: "לאן נוסעים?",
      currentLocation: "המיקום הנוכחי",
      recent: "יעדים אחרונים",
      favorites: "מועדפים",
      saveFavorite: "שמירה למועדפים",
      removeFavorite: "הסרה מהמועדפים",
      planRoute: "הצג מסלולים",
      start: "התחלה",
      stop: "סיום ניווט",
      retry: "נסה שוב",
      cancel: "ביטול",
      route: {
        fastest: "המהיר ביותר",
        balancedShade: "צל מאוזן",
        maximumShade: "מקסימום צל",
        fewerLights: "פחות רמזורים",
        saferStreets: "רחובות בטוחים",
        transitRecommended: "המסלול המומלץ",
      },
      mode: {
        walk: "הליכה",
        bike: "אופניים",
        scooter: "קורקינט",
        car: "רכב",
        motorcycle: "אופנוע",
        truck: "משאית",
        transit: "תחבורה ציבורית",
        bike_transit: "אופניים + תחב״צ",
        scooter_transit: "קורקינט + תחב״צ",
        rental_transit: "שיתופי + תחב״צ",
      },
      preference: {
        fastest: "מהיר",
        balanced_shade: "צל מאוזן",
        maximum_shade: "מקסימום צל",
        fewer_lights: "פחות רמזורים",
        safer_streets: "בטוח יותר",
        fewer_transfers: "פחות החלפות",
      },
      metrics: {
        minutes: "{{value}} דק׳",
        kilometers: "{{value}} ק״מ",
        shade: "{{value}}% צל",
        sun: "{{value}} דק׳ בשמש",
        signalsAvoided: "{{value}} רמזורים פחות",
        transfers: "{{value}} החלפות",
      },
      status: {
        searching: "מחפש מקומות…",
        planning: "מחשב את המסלולים הטובים ביותר…",
        warming: "מפעיל את מנוע הניווט… הפעולה עשויה להימשך עד דקה.",
        recalculating: "מחשב מסלול מחדש…",
        offline: "אין חיבור. ממשיכים עם המסלול השמור.",
        arrived: "הגעת ליעד",
        demo: "נתוני הדגמה — לא לשימוש בניווט אמיתי",
      },
      navigation: {
        depart: "צאו לכיוון {{street}}",
        turn: "{{modifier}} אל {{street}}",
        arrive: "היעד נמצא לפניכם",
        straight: "המשיכו ישר",
        left: "פנו שמאלה",
        right: "פנו ימינה",
        slight_left: "פנו קלות שמאלה",
        slight_right: "פנו קלות ימינה",
        uturn: "בצעו פניית פרסה",
      },
      accessibility: {
        routeCard: "מסלול {{name}}, {{duration}}, {{distance}}",
      },
      error: {
        title: "לא הצלחנו לחשב מסלול",
        generic: "משהו השתבש. אפשר לנסות שוב.",
        noDestination: "בחרו יעד תחילה.",
        permission: "נדרשת הרשאת מיקום כדי להתחיל ניווט.",
      },
      language: "English",
    },
  },
  en: {
    translation: {
      appName: "Naviz",
      tagline: "A smarter way through the city",
      searchPlaceholder: "Where to?",
      currentLocation: "Current location",
      recent: "Recent destinations",
      favorites: "Favorites",
      saveFavorite: "Save to favorites",
      removeFavorite: "Remove from favorites",
      planRoute: "Show routes",
      start: "Start",
      stop: "End navigation",
      retry: "Try again",
      cancel: "Cancel",
      route: {
        fastest: "Fastest",
        balancedShade: "Balanced shade",
        maximumShade: "Maximum shade",
        fewerLights: "Fewer lights",
        saferStreets: "Safer streets",
        transitRecommended: "Recommended",
      },
      mode: {
        walk: "Walk",
        bike: "Bike",
        scooter: "Scooter",
        car: "Drive",
        motorcycle: "Motorcycle",
        truck: "Truck",
        transit: "Transit",
        bike_transit: "Bike + transit",
        scooter_transit: "Scooter + transit",
        rental_transit: "Shared + transit",
      },
      preference: {
        fastest: "Fastest",
        balanced_shade: "Balanced shade",
        maximum_shade: "Maximum shade",
        fewer_lights: "Fewer lights",
        safer_streets: "Safer streets",
        fewer_transfers: "Fewer transfers",
      },
      metrics: {
        minutes: "{{value}} min",
        kilometers: "{{value}} km",
        shade: "{{value}}% shade",
        sun: "{{value}} min in sun",
        signalsAvoided: "{{value}} fewer lights",
        transfers: "{{value}} transfers",
      },
      status: {
        searching: "Searching places…",
        planning: "Calculating the best routes…",
        warming: "Starting the routing engine… this can take up to a minute.",
        recalculating: "Recalculating…",
        offline: "Offline. Continuing with the saved route.",
        arrived: "You have arrived",
        demo: "Demo data — not for real navigation",
      },
      navigation: {
        depart: "Head toward {{street}}",
        turn: "{{modifier}} onto {{street}}",
        arrive: "Your destination is ahead",
        straight: "Continue straight",
        left: "Turn left",
        right: "Turn right",
        slight_left: "Bear left",
        slight_right: "Bear right",
        uturn: "Make a U-turn",
      },
      accessibility: {
        routeCard: "{{name}} route, {{duration}}, {{distance}}",
      },
      error: {
        title: "We couldn’t calculate a route",
        generic: "Something went wrong. You can try again.",
        noDestination: "Choose a destination first.",
        permission: "Location permission is required to start navigation.",
      },
      language: "עברית",
    },
  },
} as const;

const deviceLanguage = Localization.getLocales()[0]?.languageCode === "en" ? "en" : "he";
I18nManager.allowRTL(true);

// i18next's default singleton intentionally exposes the fluent `.use()` API.
// eslint-disable-next-line import/no-named-as-default-member
void i18n.use(initReactI18next).init({
  resources,
  lng: deviceLanguage,
  fallbackLng: "en",
  showSupportNotice: false,
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;

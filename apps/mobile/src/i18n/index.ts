import * as Localization from "expo-localization";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { I18nManager } from "react-native";

const resources = {
  he: {
    translation: {
      appName: "Naviz",
      tagline: "ניווט חכם יותר במטרופולין תל אביב",
      searchPlaceholder: "לאן נוסעים?",
      currentLocation: "המיקום הנוכחי",
      locating: "מאתר את המיקום…",
      recent: "יעדים אחרונים",
      favorites: "מועדפים",
      saveFavorite: "שמירה למועדפים",
      removeFavorite: "הסרה מהמועדפים",
      planRoute: "הצגת מסלולים",
      start: "התחלה",
      stop: "סיום ניווט",
      retry: "ניסיון חוזר",
      cancel: "ביטול",
      clear: "ניקוי",
      collapse: "צמצום",
      change: "שינוי",
      transportMode: "אמצעי תחבורה",
      collapseModes: "צמצום בחירת אמצעי התחבורה",
      changeMode: "שינוי אמצעי התחבורה",
      routePriority: "מה להעדיף? כל סוגי המסלולים יוצגו להשוואה",
      routeComparison: "השוואת מסלולים",
      routeComparisonHint:
        "בחרו מסלול להשוואה על המפה. הנתונים מוצגים לאותו זמן יציאה.",
      moreModes: "אפשרויות נוספות",
      fewerModes: "פחות אפשרויות",
      overview: "כל המסלול",
      recenter: "מרכוז",
      mute: "השתקה",
      unmute: "הפעלת קול",
      route: {
        fastest: "המהיר ביותר",
        balancedShade: "צל מאוזן",
        maximumShade: "מקסימום צל",
        fewerLights: "פחות רמזורים",
        saferStreets: "רחובות בטוחים",
        fewerTransfers: "פחות החלפות",
        fastestFewestTransfers: "הכי מהיר · הכי מעט החלפות",
        transitRecommended: "מומלץ",
        alternative: "חלופה",
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
        signals: "{{value}} רמזורים",
        transfers: "{{value}} החלפות",
        walking: "{{value}} ק״מ הליכה",
        transitDeparture: "יציאה מתוכננת ב־{{value}}",
        transitSource: "מקורות לוחות הזמנים · Transitous",
        foldBeforeBoarding: "יש לקפל ולשאת את הכלי לפני העלייה",
        arrival: "הגעה ב־{{value}}",
      },
      confidence: {
        high: "דיוק גבוה",
        medium: "דיוק בינוני",
        low: "דיוק מוגבל",
        unknown: "דיוק לא ידוע",
      },
      fallback: {
        least_exposed_route: "החשיפה הנמוכה ביותר לשמש במסגרת מגבלת העיקוף.",
        no_material_signal_reduction:
          "המסלול המהיר נבחר; החלופות לא חסכו מספיק רמזורים.",
        shade_data_temporarily_unavailable:
          "לא ניתן היה לרענן את פרטי הצל; המסלול המהיר נבחר.",
        signal_data_temporarily_unavailable:
          "לא ניתן היה לרענן את ספירת הרמזורים; המסלול המהיר נבחר.",
        rental_availability_unavailable:
          "כלים שיתופיים זמינים בקרבת מקום, אך המסלול הזה משתמש כרגע בתחבורה ציבורית בלבד.",
      },
      mobility: {
        title: "כלי שיתופי",
        loading: "טוען זמינות חיה של כלים שיתופיים…",
        available:
          "{{count}} כלים זמינים בקרבתך · הקישו על נקודה במפה לפתיחת אפליקציית המפעיל",
        noDeepLink: "פתחו את אפליקציית המפעיל כדי לשכור את הכלי.",
        openError: "לא ניתן לפתוח את אפליקציית המפעיל במכשיר הזה.",
      },
      status: {
        searching: "מחפש מקומות…",
        planning: "מחשב מסלולים…",
        warming: "מפעיל את מנוע הניווט…",
        recalculating: "מחשב מסלול מחדש…",
        offline: "אין חיבור. ממשיכים עם המסלול השמור; חישוב מחדש דורש חיבור.",
        arrived: "הגעת ליעד",
        keepOpen:
          "הניווט פעיל. כדי לקבל הנחיות כשהמסך כבוי, יש לאפשר מיקום ברקע.",
      },
      navigation: {
        literal: "{{modifier}} {{street}}",
        depart: "צאו לכיוון {{street}}",
        turn: "{{modifier}} אל {{street}}",
        arrive: "היעד נמצא לפניכם",
        board: "עלו על {{street}}",
        straight: "המשיכו ישר",
        depart_direction: "צאו לדרך",
        left: "פנו שמאלה",
        right: "פנו ימינה",
        slight_left: "פנו מעט שמאלה",
        slight_right: "פנו מעט ימינה",
        uturn: "בצעו פניית פרסה",
      },
      accessibility: {
        routeCard: "מסלול {{name}}, {{duration}}, {{distance}}",
        map: "מפת Naviz",
      },
      empty: {
        search: "לא נמצאו תוצאות באזור הכיסוי. נסו כתובת או שם מקום אחר.",
        start: "חפשו יעד או בחרו יעד אחרון.",
      },
      error: {
        title: "לא הצלחנו להשלים את הפעולה",
        generic: "משהו השתבש. אפשר לנסות שוב.",
        noDestination: "בחרו יעד תחילה.",
        permission: "יש לאפשר גישה למיקום כדי לנווט מהמיקום הנוכחי.",
        locationUnavailable:
          "לא הצלחנו לקבוע את המיקום. ודאו ששירותי המיקום פעילים ונסו שוב.",
        outsideCoverage: "Naviz פועל כרגע במטרופולין תל אביב והסביבה.",
        code: {
          outside_coverage:
            "הנקודה נמצאת מחוץ לאזור הכיסוי של מטרופולין תל אביב.",
          routing_unavailable:
            "שירות חישוב המסלול אינו זמין כרגע. נסו שוב בעוד רגע.",
          no_route: "לא נמצא מסלול מתאים למצב ולהעדפות שנבחרו.",
          network_error: "אין חיבור לשרת. בדקו את החיבור ונסו שוב.",
          validation_error: "פרטי המסלול אינם תקינים.",
        },
      },
      language: "English",
    },
  },
  en: {
    translation: {
      appName: "Naviz",
      tagline: "Smarter navigation across metropolitan Tel Aviv",
      searchPlaceholder: "Where to?",
      currentLocation: "Current location",
      locating: "Finding your location…",
      recent: "Recent destinations",
      favorites: "Favorites",
      saveFavorite: "Save to favorites",
      removeFavorite: "Remove from favorites",
      planRoute: "Show routes",
      start: "Start",
      stop: "End navigation",
      retry: "Try again",
      cancel: "Cancel",
      clear: "Clear",
      collapse: "Collapse",
      change: "Change",
      transportMode: "Travel mode",
      collapseModes: "Collapse travel-mode choices",
      changeMode: "Change travel mode",
      routePriority:
        "Prioritize a route type; all calculated types will be shown",
      routeComparison: "Compare routes",
      routeComparisonHint:
        "Select a route to compare it on the map. Metrics use the same departure time.",
      moreModes: "More travel modes",
      fewerModes: "Fewer travel modes",
      overview: "Overview",
      recenter: "Recenter",
      mute: "Mute",
      unmute: "Unmute",
      route: {
        fastest: "Fastest",
        balancedShade: "Balanced shade",
        maximumShade: "Maximum shade",
        fewerLights: "Fewer lights",
        saferStreets: "Safer streets",
        fewerTransfers: "Fewer transfers",
        fastestFewestTransfers: "Fastest · fewest transfers",
        transitRecommended: "Recommended",
        alternative: "Alternative",
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
        signals: "{{value}} lights",
        transfers: "{{value}} transfers",
        walking: "{{value}} km walking",
        transitDeparture: "Scheduled {{value}}",
        transitSource: "Timetable sources · Transitous",
        foldBeforeBoarding: "Fold and carry before boarding",
        arrival: "Arrive at {{value}}",
      },
      confidence: {
        high: "High confidence",
        medium: "Medium confidence",
        low: "Limited confidence",
        unknown: "Unknown confidence",
      },
      fallback: {
        least_exposed_route: "Lowest sun exposure within your detour limit.",
        no_material_signal_reduction:
          "Fastest route selected; alternatives did not avoid enough lights.",
        shade_data_temporarily_unavailable:
          "Shade details could not be refreshed; fastest route selected.",
        signal_data_temporarily_unavailable:
          "Traffic-light counts could not be refreshed; fastest route selected.",
        rental_availability_unavailable:
          "Shared vehicles are nearby, but this route currently uses public transit only.",
      },
      mobility: {
        title: "Shared vehicle",
        loading: "Loading live shared vehicles…",
        available:
          "{{count}} vehicles nearby · tap a map dot to open the operator app",
        noDeepLink: "Open the operator app to rent this vehicle.",
        openError: "The operator app could not be opened on this device.",
      },
      status: {
        searching: "Searching places…",
        planning: "Calculating routes…",
        warming: "Starting the routing engine…",
        recalculating: "Recalculating…",
        offline:
          "Offline. Continuing on the saved route; rerouting requires a connection.",
        arrived: "You have arrived",
        keepOpen:
          "Navigation is active. Allow background location for guidance with the screen off.",
      },
      navigation: {
        literal: "{{modifier}} {{street}}",
        depart: "Head toward {{street}}",
        turn: "{{modifier}} onto {{street}}",
        arrive: "Your destination is ahead",
        board: "Board {{street}}",
        straight: "Continue straight",
        depart_direction: "Start your trip",
        left: "Turn left",
        right: "Turn right",
        slight_left: "Bear left",
        slight_right: "Bear right",
        uturn: "Make a U-turn",
      },
      accessibility: {
        routeCard: "{{name}} route, {{duration}}, {{distance}}",
        map: "Naviz map",
      },
      empty: {
        search:
          "No results in the coverage area. Try another address or place name.",
        start: "Search for a destination or choose a recent place.",
      },
      error: {
        title: "We couldn't complete that",
        generic: "Something went wrong. You can try again.",
        noDestination: "Choose a destination first.",
        permission:
          "Allow location access to navigate from your current position.",
        locationUnavailable:
          "We couldn't determine your location. Check Location Services and try again.",
        outsideCoverage:
          "Naviz currently covers metropolitan Tel Aviv and nearby cities.",
        code: {
          outside_coverage:
            "That point is outside the metropolitan Tel Aviv coverage area.",
          routing_unavailable:
            "Routing is temporarily unavailable. Please try again shortly.",
          no_route: "No route was found for the selected mode and preferences.",
          network_error:
            "The server cannot be reached. Check your connection and try again.",
          validation_error: "The route details are invalid.",
        },
      },
      language: "עברית",
    },
  },
} as const;

const deviceLanguage =
  Localization.getLocales()[0]?.languageCode === "en" ? "en" : "he";
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

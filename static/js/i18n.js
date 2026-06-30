/* Bilingual (English / Arabic) UI strings and language switching. */
const I18N = {
  en: {
    app_title: "Entity Scraper",
    nav_new: "New Search",
    nav_history: "History",
    footer: "Entity Scraper · search · scrape · store",

    hero_title: "Find & extract entity contact data",
    hero_sub: "Search for companies, schools, universities, academies or any organisation and automatically collect names, phones, emails, people and positions.",

    label_query: "What are you looking for?",
    ph_query: "e.g. real estate companies, private schools, software firms",
    label_location: "Location (optional)",
    ph_location: "e.g. Riyadh, Saudi Arabia",
    label_type: "Entity type (optional)",
    ph_type: "e.g. company, university, academy, hospital",
    label_max: "Number of websites to scan",
    btn_search: "Start Search",
    btn_searching: "Searching…",

    backends_title: "Active search backend",
    backend_free: "Free DuckDuckGo (no key)",
    backend_google: "Google API",
    backend_serpapi: "SerpAPI",
    backend_llm: "LLM assist",
    backend_on: "available",
    backend_off: "not configured",

    progress_title: "Progress",
    results_title: "Results",
    no_results: "No results yet.",
    col_name: "Name",
    col_contact: "Contact",
    col_people: "People",
    col_website: "Website",
    people_count: "people",
    phones: "Phones",
    emails: "Emails",
    address: "Address",
    social: "Social",
    people: "People & positions",
    description: "Description",
    view_details: "Details",
    visit_site: "Visit site",
    btn_export: "Download JSON",
    position: "Position",

    history_title: "Search History",
    th_id: "#",
    th_query: "Query",
    th_status: "Status",
    th_count: "Results",
    th_date: "Date",
    th_actions: "Actions",
    open: "Open",
    delete: "Delete",
    confirm_delete: "Delete this search and its data?",
    no_history: "No searches yet. Start one from the New Search page.",
    back: "Back to history",

    status_pending: "Pending",
    status_running: "Running",
    status_completed: "Completed",
    status_failed: "Failed",
    loading: "Loading…",
  },
  ar: {
    app_title: "باحث الكيانات",
    nav_new: "بحث جديد",
    nav_history: "السجل",
    footer: "باحث الكيانات · بحث · استخراج · تخزين",

    hero_title: "ابحث واستخرج بيانات التواصل للكيانات",
    hero_sub: "ابحث عن الشركات والمدارس والجامعات والأكاديميات أو أي مؤسسة، واجمع تلقائيًا الأسماء وأرقام الهواتف والبريد الإلكتروني والأشخاص ومناصبهم.",

    label_query: "ماذا تبحث عنه؟",
    ph_query: "مثال: شركات عقارية، مدارس خاصة، شركات برمجيات",
    label_location: "الموقع (اختياري)",
    ph_location: "مثال: الرياض، المملكة العربية السعودية",
    label_type: "نوع الكيان (اختياري)",
    ph_type: "مثال: شركة، جامعة، أكاديمية، مستشفى",
    label_max: "عدد المواقع المراد فحصها",
    btn_search: "ابدأ البحث",
    btn_searching: "جارٍ البحث…",

    backends_title: "محرك البحث النشط",
    backend_free: "DuckDuckGo المجاني (بدون مفتاح)",
    backend_google: "Google API",
    backend_serpapi: "SerpAPI",
    backend_llm: "مساعدة LLM",
    backend_on: "متاح",
    backend_off: "غير مُعدّ",

    progress_title: "التقدم",
    results_title: "النتائج",
    no_results: "لا توجد نتائج بعد.",
    col_name: "الاسم",
    col_contact: "التواصل",
    col_people: "الأشخاص",
    col_website: "الموقع",
    people_count: "أشخاص",
    phones: "الهواتف",
    emails: "البريد الإلكتروني",
    address: "العنوان",
    social: "وسائل التواصل",
    people: "الأشخاص والمناصب",
    description: "الوصف",
    view_details: "التفاصيل",
    visit_site: "زيارة الموقع",
    btn_export: "تنزيل JSON",
    position: "المنصب",

    history_title: "سجل عمليات البحث",
    th_id: "#",
    th_query: "الاستعلام",
    th_status: "الحالة",
    th_count: "النتائج",
    th_date: "التاريخ",
    th_actions: "إجراءات",
    open: "فتح",
    delete: "حذف",
    confirm_delete: "هل تريد حذف هذا البحث وبياناته؟",
    no_history: "لا توجد عمليات بحث بعد. ابدأ واحدة من صفحة البحث الجديد.",
    back: "العودة إلى السجل",

    status_pending: "قيد الانتظار",
    status_running: "قيد التشغيل",
    status_completed: "مكتمل",
    status_failed: "فشل",
    loading: "جارٍ التحميل…",
  },
};

let CURRENT_LANG = localStorage.getItem("lang") || "en";

function t(key) {
  return (I18N[CURRENT_LANG] && I18N[CURRENT_LANG][key]) || I18N.en[key] || key;
}

function applyTranslations() {
  document.documentElement.lang = CURRENT_LANG;
  document.documentElement.dir = CURRENT_LANG === "ar" ? "rtl" : "ltr";

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph")));
  });

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === CURRENT_LANG);
  });

  // Let page-specific code re-render dynamic content.
  document.dispatchEvent(new CustomEvent("langchange", { detail: { lang: CURRENT_LANG } }));
}

function setLang(lang) {
  CURRENT_LANG = lang;
  localStorage.setItem("lang", lang);
  applyTranslations();
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => setLang(btn.dataset.lang));
  });
  applyTranslations();
});

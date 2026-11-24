// Observable Framework configuration. Source root is site/, build output is dist/.
// Framework generates relative links, so the built site works under any sub-path on GitHub Pages.
export default {
  root: "site",
  output: "dist",
  title: "Nightlights Explorer",
  theme: ["air", "alt", "wide"], // light page; the map has its own dark surface
  sidebar: false,
  toc: false,
  pager: false,
  pages: [],
  // Google Analytics (GA4), on every page, as on drywet-explorer. Not loaded on localhost, so that
  // previews and the reviewers' browser runs are not counted as visits.
  head: `<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%2210.5%22 fill=%22%2310151c%22/%3E%3Cpath d=%22M12 1.5a10.500 10.500 0 0 1 0 21 13.500 13.500 0 0 0 0-21Z%22 fill=%22%232a3644%22/%3E%3Ccircle cx=%228.300%22 cy=%229.400%22 r=%223%22 fill=%22%23ffd76a%22 opacity=%22.22%22/%3E%3Ccircle cx=%228.300%22 cy=%229.400%22 r=%221.500%22 fill=%22%23ffd76a%22/%3E%3Ccircle cx=%2212.700%22 cy=%2213.700%22 r=%221.100%22 fill=%22%23ffd76a%22/%3E%3Ccircle cx=%227.300%22 cy=%2214.900%22 r=%22.800%22 fill=%22%23f2b24a%22/%3E%3Ccircle cx=%2211.300%22 cy=%226.700%22 r=%22.600%22 fill=%22%23f2b24a%22/%3E%3Ccircle cx=%2210.200%22 cy=%2217.600%22 r=%22.600%22 fill=%22%23f2b24a%22/%3E%3C/svg%3E">
<script>
  if (!["localhost", "127.0.0.1"].includes(location.hostname)) {
    const s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=G-M3ZZ0H7XHJ";
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-M3ZZ0H7XHJ');
  }
</script>`,
  footer: 'Developed by <a href="https://benny.istan.to" target="_blank" rel="noopener">Benny Istanto</a> as a casual weekend project. Night-time lights from NASA Black Marble, Collection 2 (VNP46A3 monthly, VNP46A2 daily, view angles from VNP46A1). Long view: DMSP-OLS stable lights processed by the Earth Observation Group, Payne Institute, Colorado School of Mines; DMSP data collected by the US Air Force Weather Agency. Roads on the Mudik map: OpenStreetMap contributors. Admin boundaries: Badan Informasi Geospasial. Built with Observable Framework.'
};

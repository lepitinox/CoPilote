"use strict";
// Indicateurs : graphiques SVG tracés à la main à partir des sprints saisis.
// Deux séries au plus par graphique, couleurs fixes par rôle (bleu : mesure principale,
// orange : mesure de comparaison), un seul axe vertical, valeurs lisibles au survol.

const C1 = "var(--serie-1)", C1_CLAIR = "var(--serie-1-clair)", C2 = "var(--serie-2)";

function graduation(max) {
  if (max <= 0) return { haut: 1, pas: 1 };
  const brut = max / 4, puissance = Math.pow(10, Math.floor(Math.log10(brut)));
  const pas = [1, 2, 2.5, 5, 10].map(m => m * puissance).find(p => p >= brut);
  return { haut: Math.ceil(max / pas) * pas, pas };
}

/**
 * options : { titre, sous, categories: [libellé], series: [{ nom, couleur, type: "ligne"|"barre", valeurs }],
 *             seuil: { valeur, libelle }, repereX: { index, libelle }, max, suffixe }
 */
function graphe(o) {
  const L = 540, H = 240, g = { g: 44, d: 86, h: 14, b: 30 };
  const n = o.categories.length, larg = (L - g.g - g.d) / Math.max(n, 1), haut = H - g.h - g.b;
  const toutes = o.series.flatMap(s => s.valeurs).filter(v => v != null);
  const { haut: max, pas } = o.max ? { haut: o.max, pas: o.max / (o.max <= 5 ? o.max : 4) }
    : graduation(Math.max(...toutes, o.seuil ? o.seuil.valeur : 0, 0));
  const x = i => g.g + larg * (i + 0.5), y = v => g.h + haut * (1 - v / max);
  const svg = el("svg:svg", { viewBox: `0 0 ${L} ${H}`, role: "img", "aria-label": `${o.titre}. ${o.sous || ""}` });
  const texte = (px, py, t, extra = {}) => el("svg:text", { x: px, y: py, "font-size": 11.5, fill: "var(--doux)", ...extra }, t);

  for (let v = 0; v <= max + 1e-9; v += pas) {
    svg.append(el("svg:line", { x1: g.g, x2: L - g.d, y1: y(v), y2: y(v), stroke: v === 0 ? "#b8c0cb" : "#eef0f3", "stroke-width": 1 }),
      texte(g.g - 6, y(v) + 4, nb(Math.round(v * 100) / 100) + (o.suffixe || ""), { "text-anchor": "end" }));
  }
  const saut = Math.ceil(n / 12);
  o.categories.forEach((c, i) => { if (i % saut === 0) svg.append(texte(x(i), H - 10, c, { "text-anchor": "middle" })); });

  const barres = o.series.filter(s => s.type === "barre");
  for (let i = 0; i < n; i++) {
    const presentes = barres.filter(s => s.valeurs[i] != null);
    const lb = Math.min(34, (larg - 8) / Math.max(presentes.length, 1));
    presentes.forEach((s, k) => {
      const v = s.valeurs[i], h = Math.max(haut * (v / max), v > 0 ? 1 : 0), r = Math.min(4, h, lb / 2);
      const x0 = x(i) - (presentes.length * lb) / 2 + k * lb + 1, w = lb - 2, y0 = y(0) - h;
      svg.append(el("svg:path", { fill: s.couleur,
        d: `M${x0},${y(0)}V${y0 + r}Q${x0},${y0} ${x0 + r},${y0}H${x0 + w - r}Q${x0 + w},${y0} ${x0 + w},${y0 + r}V${y(0)}Z` }));
    });
  }
  const etiquettes = [];
  o.series.filter(s => s.type === "ligne").forEach(s => {
    const pts = s.valeurs.map((v, i) => (v == null ? null : [x(i), y(v)])).filter(Boolean);
    if (!pts.length) return;
    svg.append(el("svg:polyline", { points: pts.map(p => p.join(",")).join(" "), fill: "none", stroke: s.couleur,
      "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    pts.forEach(p => svg.append(el("svg:circle", { cx: p[0], cy: p[1], r: 4, fill: s.couleur, stroke: "var(--carte)", "stroke-width": 2 })));
    etiquettes.push([pts[pts.length - 1], s.nom]);
  });
  // Étiquettes directes en bout de ligne, écartées si elles se chevauchent.
  etiquettes.sort((a, b) => a[0][1] - b[0][1]);
  etiquettes.forEach((e, i) => { if (i && e[0][1] - etiquettes[i - 1][2] < 13) e[2] = etiquettes[i - 1][2] + 13; else e[2] = e[0][1]; });
  etiquettes.forEach(([p, nom, py]) => svg.append(texte(p[0] + 9, py + 4, nom, { fill: "var(--texte)" })));

  if (o.seuil) svg.append(
    el("svg:line", { x1: g.g, x2: L - g.d, y1: y(o.seuil.valeur), y2: y(o.seuil.valeur), stroke: "var(--texte)", "stroke-width": 1.5, "stroke-dasharray": "5 4" }),
    texte(L - g.d + 6, y(o.seuil.valeur) + 4, o.seuil.libelle, { fill: "var(--texte)" }));
  if (o.repereX && o.repereX.index < n) svg.append(
    el("svg:line", { x1: x(o.repereX.index), x2: x(o.repereX.index), y1: g.h, y2: y(0), stroke: "var(--texte)", "stroke-width": 1.5, "stroke-dasharray": "5 4" }),
    texte(x(o.repereX.index) + 5, g.h + 10, o.repereX.libelle, { fill: "var(--texte)" }));

  // Survol et clavier : une zone par catégorie, plus large que les marques.
  const bulle = el("div", { class: "bulle" });
  const guide = el("svg:line", { y1: g.h, y2: y(0), stroke: "#b8c0cb", "stroke-width": 1, visibility: "hidden" });
  svg.append(guide);
  const carte = el("div", { class: "carte graphe" });
  const montrer = i => {
    const lignes = o.series.filter(s => s.valeurs[i] != null);
    if (!lignes.length && !(o.complement && o.complement(i))) return cacher();
    bulle.replaceChildren(el("b", {}, o.categories[i]),
      lignes.map(s => el("div", {}, el("i", { style: "background:" + s.couleur }), `${s.nom} : ${nb(s.valeurs[i])}${o.suffixe || ""}`)),
      o.complement && o.complement(i) ? el("div", { style: "opacity:.8" }, o.complement(i)) : null);
    bulle.style.display = "block";
    const cadre = svg.getBoundingClientRect(), base = carte.getBoundingClientRect();
    const gauche = cadre.left - base.left + (x(i) / L) * cadre.width;
    bulle.style.left = Math.min(Math.max(gauche - bulle.offsetWidth / 2, 4), base.width - bulle.offsetWidth - 4) + "px";
    bulle.style.top = cadre.top - base.top + 4 + "px";
    guide.setAttribute("x1", x(i)); guide.setAttribute("x2", x(i)); guide.setAttribute("visibility", "visible");
  };
  const cacher = () => { bulle.style.display = "none"; guide.setAttribute("visibility", "hidden"); };
  o.categories.forEach((c, i) => svg.append(el("svg:rect", { x: g.g + larg * i, y: g.h, width: larg, height: haut, fill: "transparent",
    tabindex: 0, "aria-label": c, onmouseenter: () => montrer(i), onmouseleave: cacher, onfocus: () => montrer(i), onblur: cacher })));

  carte.append(el("h3", {}, o.titre), el("p", { class: "sous" }, o.sous || ""), svg,
    o.series.length > 1 || o.series.some(s => s.type === "barre" && o.legendeForcee)
      ? el("div", { class: "legende" }, o.series.map(s => el("span", {}, el("i", { style: "background:" + s.couleur }), s.nom))) : null,
    bulle);
  return carte;
}

VUES.kpi = ["Indicateurs", "Pilotage", async v => {
  const [sprints, s, m] = await Promise.all([api("GET", "sprint"), api("GET", "synthese"), api("GET", "mission")]);
  v.append(titreVue("Indicateurs",
    "Les KPI qui disent si la trajectoire tient : vélocité, atterrissage, périmètre, qualité, moral. Survolez un sprint pour lire ses valeurs ; le tableau complet est dans la vue Sprints.",
    el("button", { onclick: () => afficher("sprints") }, "Voir le tableau")));
  if (!sprints.length) { v.append(el("div", { class: "vide" }, "Aucun sprint saisi.")); return; }
  const k = s.kpi, a = s.atterrissage, cat = sprints.map(x => "S" + x.numero);
  const col = cle => sprints.map(x => (typeof x[cle] === "number" ? x[cle] : null));
  v.append(el("div", { class: "grille", style: "margin-bottom:14px" },
    tuile("Vélocité moyenne", nb(k.velocite_moyenne) + " pts", `sur les ${k.nb_sprints_moyenne} derniers sprints`),
    tuile("Prédictibilité", pct(k.predictibilite), "réalisé / prévu, en moyenne"),
    tuile("Fin estimée", a.atteignable ? dateFr(a.date_fin_estimee) : "Non calculable",
      a.atteignable && a.ecart_sprints != null ? (a.ecart_sprints ? `+${a.ecart_sprints} sprints après la cible` : "Dans la cible") : "Le backlog ne se vide pas assez vite"),
    tuile("Anomalies en stock", nb(k.solde_anomalies), "créées moins corrigées, depuis le sprint 1")));

  // Atterrissage : reste à faire réel, puis projection à consommation nette constante.
  const PROJ_MAX = 14, restes = col("reste"), catA = [...cat], reel = [...restes], proj = restes.map(() => null);
  const dernier = sprints[sprints.length - 1], duree = m.duree_sprint_jours || 14;
  if (a.atteignable && a.consommation_nette > 0) {
    for (let i = 1, r = a.reste - a.consommation_nette; i <= PROJ_MAX; i++, r -= a.consommation_nette) {
      catA.push("S" + (dernier.numero + i)); reel.push(null); proj.push(Math.max(Math.round(r), 0));
      if (r <= 0) break;
    }
  }
  let repereX = null;
  const fin = jour(dernier.date_fin), cible = jour(a.date_cible);
  if (fin && cible) {
    const index = sprints.length - 1 + Math.ceil((cible - fin) / 864e5 / duree);
    if (index >= 0 && index < catA.length) repereX = { index, libelle: "Cible : " + dateFr(a.date_cible) };
  }
  const tronque = a.atteignable && a.sprints_restants > PROJ_MAX;

  v.append(el("div", { class: "graphes" },
    graphe({ titre: "Vélocité", sous: "Points prévus et réalisés par sprint", categories: cat, series: [
      { nom: "Réalisé", couleur: C1, type: "ligne", valeurs: col("realise") },
      { nom: "Prévu", couleur: C2, type: "ligne", valeurs: col("prevu") }],
      complement: i => (sprints[i].prevu > 0 ? "Taux de réalisation : " + pct(sprints[i].realise / sprints[i].prevu) : null) }),
    graphe({ titre: "Atterrissage", legendeForcee: true,
      sous: a.atteignable ? `Reste à faire en points, projeté à ${nb(a.consommation_nette)} pts nets par sprint` + (tronque ? ` — projection limitée à ${PROJ_MAX} sprints` : "")
        : "Reste à faire en points — aucune projection : le backlog ne se vide pas assez vite",
      categories: catA, repereX, series: [
        { nom: "Reste à faire", couleur: C1, type: "barre", valeurs: reel },
        { nom: "Projection", couleur: C1_CLAIR, type: "barre", valeurs: proj }] }),
    graphe({ titre: "Périmètre", sous: "Points ajoutés au backlog pendant le sprint", categories: cat,
      seuil: { valeur: s.seuils.marge_ajout, libelle: "Marge : " + nb(s.seuils.marge_ajout) },
      series: [{ nom: "Points ajoutés", couleur: C1, type: "barre", valeurs: col("ajoute") }] }),
    graphe({ titre: "Qualité", sous: "Anomalies créées et corrigées par sprint", categories: cat, series: [
      { nom: "Corrigées", couleur: C1, type: "barre", valeurs: col("anomalies_corrigees") },
      { nom: "Créées", couleur: C2, type: "barre", valeurs: col("anomalies_creees") }] }),
    graphe({ titre: "Taux de réalisation", sous: "Points réalisés rapportés aux points prévus", categories: cat, suffixe: " %",
      seuil: { valeur: Math.round(s.seuils.taux_realisation_min * 100), libelle: "Seuil : " + Math.round(s.seuils.taux_realisation_min * 100) + " %" },
      series: [{ nom: "Taux de réalisation", couleur: C1, type: "ligne",
        valeurs: sprints.map(x => (x.prevu > 0 && typeof x.realise === "number" ? Math.round((x.realise / x.prevu) * 100) : null)) }] }),
    graphe({ titre: "Moral de l'équipe", sous: "Note de 1 à 5 relevée en fin de sprint", categories: cat, max: 5,
      series: [{ nom: "Moral", couleur: C1, type: "ligne", valeurs: col("moral") }] })));
}];

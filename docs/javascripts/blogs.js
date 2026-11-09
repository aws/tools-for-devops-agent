(function () {
  // Search and filters for the Blogs page. The posts are static HTML rendered by
  // docs/hooks/blogs_catalog.py; this script only shows and hides them. Filter
  // state is kept in the URL query (q, tag, source, kind, since) so a filtered
  // view can be shared as a link.

  var FILTERS = ["q", "tag", "source", "kind", "since"];

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function field(id, label, control) {
    var wrap = el("div", { class: "blog-filter" });
    wrap.appendChild(el("label", { for: id, class: "filter-label" }, label));
    control.id = id;
    wrap.appendChild(control);
    return wrap;
  }

  function select(options) {
    var s = el("select");
    options.forEach(function (o) { s.appendChild(el("option", { value: o[0] }, o[1])); });
    return s;
  }

  function countBy(items, read) {
    var counts = {};
    items.forEach(function (item) {
      read(item).forEach(function (v) { counts[v] = (counts[v] || 0) + 1; });
    });
    return Object.keys(counts).sort(function (a, b) {
      return counts[b] - counts[a] || a.localeCompare(b);
    }).map(function (k) { return [k, k + " (" + counts[k] + ")"]; });
  }

  function cutoff(months) {
    var d = new Date();
    d.setMonth(d.getMonth() - Number(months));
    return d.toISOString().slice(0, 10);
  }

  function initBlogs() {
    var root = document.getElementById("blog-filters");
    if (!root || root.dataset.ready) return;
    root.dataset.ready = "1";

    var items = Array.prototype.slice.call(document.querySelectorAll(".blog-post"));
    var lists = Array.prototype.slice.call(document.querySelectorAll(".blog-list"));
    var tagsOf = function (i) { return i.dataset.tags.split("|"); };

    var controls = {
      q: el("input", { type: "search", placeholder: "Title, author or keyword", autocomplete: "off" }),
      tag: select([["", "All tags"]].concat(countBy(items, tagsOf))),
      source: select([["", "All sources"]].concat(countBy(items, function (i) { return [i.dataset.source]; }))),
      kind: select([["", "AWS and community"], ["aws", "AWS only"], ["community", "Community only"]]),
      since: select([["", "Any time"], ["3", "Last 3 months"], ["6", "Last 6 months"], ["12", "Last 12 months"]])
    };

    var form = el("form", { class: "blog-filters-form", role: "search" });
    form.addEventListener("submit", function (ev) { ev.preventDefault(); });
    form.appendChild(field("blog-q", "Search", controls.q));
    form.appendChild(field("blog-tag", "Tag", controls.tag));
    form.appendChild(field("blog-source", "Source", controls.source));
    form.appendChild(field("blog-kind", "Published by", controls.kind));
    form.appendChild(field("blog-since", "Published", controls.since));
    var reset = el("button", { type: "button", class: "filter-btn" }, "Clear filters");
    form.appendChild(reset);

    var status = el("p", { class: "blog-count", "aria-live": "polite" });
    var empty = el("p", { class: "blog-empty", hidden: "" }, "No posts match these filters.");
    root.appendChild(form);
    root.appendChild(status);
    root.appendChild(empty);

    var params = new URLSearchParams(window.location.search);
    FILTERS.forEach(function (k) {
      var v = params.get(k);
      if (!v) return;
      // Only accept values the page offers, so a crafted link cannot select nothing silently.
      if (k === "q" || Array.prototype.some.call(controls[k].options, function (o) { return o.value === v; })) {
        controls[k].value = v;
      }
    });

    function apply() {
      var q = controls.q.value.trim().toLowerCase();
      var since = controls.since.value ? cutoff(controls.since.value) : "";
      var shown = 0;
      items.forEach(function (item) {
        var ok = (!q || item.textContent.toLowerCase().indexOf(q) !== -1) &&
          (!controls.tag.value || tagsOf(item).indexOf(controls.tag.value) !== -1) &&
          (!controls.source.value || item.dataset.source === controls.source.value) &&
          (!controls.kind.value || item.dataset.kind === controls.kind.value) &&
          (!since || item.dataset.date >= since);
        item.hidden = !ok;
        if (ok) shown++;
      });
      lists.forEach(function (list) {
        var visible = list.querySelector(".blog-post:not([hidden])") !== null;
        list.hidden = !visible;
        var heading = document.getElementById(list.dataset.format);
        if (heading) heading.hidden = !visible;
        document.querySelectorAll('.md-nav--secondary a[href$="#' + list.dataset.format + '"]').forEach(function (a) {
          a.parentElement.hidden = !visible;
        });
      });
      status.textContent = "Showing " + shown + " of " + items.length + " posts";
      empty.hidden = shown !== 0;

      var next = new URLSearchParams();
      FILTERS.forEach(function (k) { if (controls[k].value) next.set(k, controls[k].value); });
      var query = next.toString();
      history.replaceState(null, "", window.location.pathname + (query ? "?" + query : "") + window.location.hash);
    }

    controls.q.addEventListener("input", apply);
    ["tag", "source", "kind", "since"].forEach(function (k) {
      controls[k].addEventListener("change", apply);
    });
    reset.addEventListener("click", function () {
      FILTERS.forEach(function (k) { controls[k].value = ""; });
      apply();
    });
    document.querySelectorAll(".blog-tag").forEach(function (button) {
      button.setAttribute("aria-label", "Show posts tagged " + button.dataset.tag);
      button.addEventListener("click", function () {
        controls.tag.value = button.dataset.tag;
        apply();
        root.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });

    apply();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initBlogs);
  } else {
    initBlogs();
  }

  // Material instant navigation
  if (typeof document$ !== "undefined") {
    document$.subscribe(initBlogs);
  }
})();

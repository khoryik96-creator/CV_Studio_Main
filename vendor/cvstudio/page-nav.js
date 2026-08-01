// ── Optional pinned main navigation ───────────────────────────────────────────
// v24.6.154: the opt-in pin keeps the feature panel at the top and gives the
// active feature page a dedicated vertical scroll viewport directly below it.
// This prevents long Dashboard/OneNote/other pages from sliding underneath the
// navigation. Both the floating panel and active view are portalled to body to
// escape the legacy mixed .app/body stacking contexts.
var PAGE_NAV_PIN_STORE = 'cvstudio_page_nav_pinned_v1';
var _pageNavPinEnabled = false;
var _pageNavPinTicking = false;
var _pageNavScrollView = null;
var _pageNavScrollViewHome = null;
var _pageNavScrollByView = {};
var _pageNavScrollModeStartY = 0;
var _pageNavScrollModeContentTop = 0;

function pageNavPinSupported() {
  return window.innerWidth > 760;
}

function pageNavPinStored() {
  try { return localStorage.getItem(PAGE_NAV_PIN_STORE) === '1'; } catch(e) { return false; }
}

function pageNavDocumentScrollTop() {
  return window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;
}

function updatePageNavPinButton() {
  var nav = document.getElementById('pageTabs');
  var btn = document.getElementById('pageNavPinToggle');
  var label = document.getElementById('pageNavPinLabel');
  if (nav) nav.classList.toggle('nav-pin-enabled', !!_pageNavPinEnabled);
  if (btn) {
    btn.setAttribute('aria-pressed', _pageNavPinEnabled ? 'true' : 'false');
    btn.title = _pageNavPinEnabled
      ? 'Pinned: feature buttons stay visible and long pages scroll below them. Click to unpin.'
      : 'Keep these feature buttons visible while scrolling';
  }
  if (label) label.textContent = _pageNavPinEnabled ? 'Pinned' : 'Pin tabs';
}

function restorePageNavHome() {
  var nav = document.getElementById('pageTabs');
  var spacer = document.getElementById('pageTabsSpacer');
  if (!nav || !spacer || !spacer.parentNode) return;
  if (nav.parentNode !== spacer.parentNode || nav.previousElementSibling !== spacer) {
    spacer.parentNode.insertBefore(nav, spacer.nextSibling);
  }
}

function pageNavRestoreScrollView(restoreDocumentPosition) {
  var view = _pageNavScrollView;
  var home = _pageNavScrollViewHome;
  if (!view) {
    document.body.classList.remove('page-nav-content-scroll-active');
    return;
  }

  var innerY = Number(view.scrollTop) || 0;
  var rememberedY = view.id ? (Number(_pageNavScrollByView[view.id]) || 0) : 0;
  // switchTab removes .active before the queued pin refresh. display:none can
  // reset scrollTop to 0, so keep the last live scroll event value in that case.
  if (!view.classList.contains('active') && rememberedY > innerY) innerY = rememberedY;
  if (view.id) _pageNavScrollByView[view.id] = innerY;
  view.classList.remove('page-nav-content-scroll');
  view.style.removeProperty('--page-nav-content-top');
  view.style.removeProperty('--page-nav-content-left');
  view.style.removeProperty('--page-nav-content-width');
  view.style.removeProperty('--page-nav-content-height');

  if (home && home.parent) {
    if (home.next && home.next.parentNode === home.parent) home.parent.insertBefore(view, home.next);
    else home.parent.appendChild(view);
  }

  _pageNavScrollView = null;
  _pageNavScrollViewHome = null;
  document.body.classList.remove('page-nav-content-scroll-active');

  if (restoreDocumentPosition && view && view.classList.contains('active')) {
    var rect = view.getBoundingClientRect();
    var docTop = rect.top + pageNavDocumentScrollTop();
    var target = Math.max(0, docTop + innerY - Math.max(8, _pageNavScrollModeContentTop));
    window.scrollTo(0, target);
  }
}

function pageNavPinActiveView(nav, spacer) {
  var active = document.querySelector('.page-view.active');
  if (!active || !nav || !spacer) {
    pageNavRestoreScrollView(false);
    return;
  }

  if (_pageNavScrollView && _pageNavScrollView !== active) {
    pageNavRestoreScrollView(false);
  }

  var firstAttach = _pageNavScrollView !== active;
  var rect;
  var initialScroll = 0;
  if (firstAttach) {
    rect = active.getBoundingClientRect();
    var currentDocY = pageNavDocumentScrollTop();
    var navBottomBefore = Math.max(8, nav.getBoundingClientRect().bottom + 8);
    var activeDocTop = rect.top + currentDocY;
    initialScroll = Object.prototype.hasOwnProperty.call(_pageNavScrollByView, active.id)
      ? (Number(_pageNavScrollByView[active.id]) || 0)
      : Math.max(0, currentDocY + navBottomBefore - activeDocTop);
    _pageNavScrollViewHome = { parent: active.parentNode, next: active.nextSibling };
    _pageNavScrollView = active;
    if (!active.__pageNavScrollMemoryBound) {
      active.__pageNavScrollMemoryBound = true;
      active.addEventListener('scroll', function(){
        if (active.id && active.classList.contains('page-nav-content-scroll')) {
          _pageNavScrollByView[active.id] = Number(active.scrollTop) || 0;
        }
      }, {passive:true});
    }
    if (active.parentNode !== document.body) document.body.appendChild(active);
    active.classList.add('page-nav-content-scroll');
  } else {
    rect = active.getBoundingClientRect();
  }

  var navRect = nav.getBoundingClientRect();
  // Keep global notifications directly below and aligned inside the pinned
  // navigation's right edge. This avoids both overlap and the detached
  // far-corner position on wide screens.
  document.body.style.setProperty('--page-nav-toast-top', Math.ceil(navRect.bottom + 12) + 'px');
  document.body.style.setProperty('--page-nav-toast-right', Math.max(12, Math.ceil(window.innerWidth - navRect.right + 12)) + 'px');
  var spacerRect = spacer.getBoundingClientRect();
  var contentTop = Math.max(8, Math.ceil(navRect.bottom + 8));
  var contentLeft = Math.round(firstAttach ? rect.left : parseFloat(active.style.getPropertyValue('--page-nav-content-left')) || spacerRect.left);
  var contentWidth = Math.round(firstAttach ? rect.width : parseFloat(active.style.getPropertyValue('--page-nav-content-width')) || spacerRect.width);

  // App-contained views align to the navigation shell. Legacy body-level views
  // (OneNote, Dashboard and later tabs) retain their wider measured footprint.
  if (_pageNavScrollViewHome && _pageNavScrollViewHome.parent && _pageNavScrollViewHome.parent.classList && _pageNavScrollViewHome.parent.classList.contains('app')) {
    contentLeft = Math.round(spacerRect.left);
    contentWidth = Math.round(spacerRect.width);
  } else if (_pageNavScrollViewHome && _pageNavScrollViewHome.parent === document.body) {
    contentLeft = 0;
    contentWidth = window.innerWidth;
  }

  var contentHeight = Math.max(180, window.innerHeight - contentTop - 8);
  active.style.setProperty('--page-nav-content-top', contentTop + 'px');
  active.style.setProperty('--page-nav-content-left', contentLeft + 'px');
  active.style.setProperty('--page-nav-content-width', contentWidth + 'px');
  active.style.setProperty('--page-nav-content-height', contentHeight + 'px');
  document.body.classList.add('page-nav-content-scroll-active');
  _pageNavScrollModeContentTop = contentTop;

  if (firstAttach) {
    active.scrollTop = initialScroll;
    // The fixed height/overflow box is established during this frame. Reapply
    // on the next frame so browsers do not clamp a restored tab position to 0.
    window.requestAnimationFrame(function(){
      if (_pageNavScrollView === active) active.scrollTop = initialScroll;
    });
  }
}

function clearPageNavFloating(restoreDocumentPosition) {
  var nav = document.getElementById('pageTabs');
  var spacer = document.getElementById('pageTabsSpacer');
  pageNavRestoreScrollView(restoreDocumentPosition !== false);
  if (nav) {
    nav.classList.remove('nav-pinned-floating');
    nav.style.removeProperty('--page-nav-pin-left');
    nav.style.removeProperty('--page-nav-pin-width');
  }
  restorePageNavHome();
  if (spacer) {
    spacer.style.display = 'none';
    spacer.style.height = '0px';
  }
  document.body.classList.remove('page-nav-floating-active');
  document.body.style.removeProperty('--page-nav-toast-top');
  document.body.style.removeProperty('--page-nav-toast-right');
}

function refreshPageNavPin() {
  _pageNavPinTicking = false;
  var nav = document.getElementById('pageTabs');
  var spacer = document.getElementById('pageTabsSpacer');
  if (!nav || !spacer) return;
  if (!_pageNavPinEnabled || !pageNavPinSupported()) {
    clearPageNavFloating(true);
    return;
  }

  var isFloating = nav.classList.contains('nav-pinned-floating');
  var scrollTop = pageNavDocumentScrollTop();

  // Once the pinned workspace is active, keep it active until the user clicks
  // Pinned to unpin (or the viewport becomes mobile). Locking body scroll can
  // otherwise clamp document scrollY and make the layout oscillate in/out.
  if (!isFloating) {
    var anchorRect = nav.getBoundingClientRect();
    var anchorTop = anchorRect.top + scrollTop;
    if (scrollTop + 8 < anchorTop) return;
  }

  var widthRect = isFloating ? spacer.getBoundingClientRect() : nav.getBoundingClientRect();
  if (!isFloating) {
    _pageNavScrollModeStartY = scrollTop;
    spacer.style.height = Math.ceil(widthRect.height) + 'px';
    spacer.style.display = 'block';
  }

  var liveRect = spacer.getBoundingClientRect();
  nav.style.setProperty('--page-nav-pin-left', Math.round(liveRect.left) + 'px');
  nav.style.setProperty('--page-nav-pin-width', Math.round(liveRect.width) + 'px');
  nav.classList.add('nav-pinned-floating');
  if (nav.parentNode !== document.body) document.body.appendChild(nav);
  document.body.classList.add('page-nav-floating-active');
  pageNavPinActiveView(nav, spacer);
}

function queuePageNavPinRefresh() {
  if (_pageNavPinTicking) return;
  _pageNavPinTicking = true;
  window.requestAnimationFrame(refreshPageNavPin);
}

function setPageNavPin(enabled, persist, notify) {
  _pageNavPinEnabled = !!enabled;
  if (persist !== false) {
    try { cvStudioDurableSettingSet(PAGE_NAV_PIN_STORE, _pageNavPinEnabled ? '1' : '0'); } catch(e) {}
  }
  updatePageNavPinButton();
  queuePageNavPinRefresh();
  if (notify && typeof showToast === 'function') {
    showToast(_pageNavPinEnabled ? 'Feature buttons pinned; long pages scroll below them' : 'Feature buttons unpinned', 'info');
  }
}

function togglePageNavPin(ev) {
  if (ev) { ev.preventDefault(); ev.stopPropagation(); }
  setPageNavPin(!_pageNavPinEnabled, true, true);
}

function initPageNavPin() {
  _pageNavPinEnabled = pageNavPinStored();
  updatePageNavPinButton();
  window.addEventListener('scroll', queuePageNavPinRefresh, {passive:true});
  document.addEventListener('scroll', function(ev){
    if (_pageNavScrollView && ev.target === _pageNavScrollView) return;
    queuePageNavPinRefresh();
  }, {passive:true, capture:true});
  window.addEventListener('resize', queuePageNavPinRefresh);
  queuePageNavPinRefresh();
}

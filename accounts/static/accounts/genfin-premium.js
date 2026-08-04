document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname.replace(/\/$/, '') || '/';
  document.querySelectorAll('.side-link').forEach(link => {
    const href = (link.getAttribute('href') || '').replace(/\/$/, '') || '/';
    if (href === path || (href !== '/' && path.startsWith(href))) {
      link.classList.add('is-active');
      link.setAttribute('aria-current', 'page');
    }
    if (!link.getAttribute('title')) link.setAttribute('title', link.textContent.trim());
  });
});

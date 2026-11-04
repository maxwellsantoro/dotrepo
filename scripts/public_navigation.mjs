// The full navigation remains visible when JavaScript is unavailable.
const toggle = document.querySelector('.nav__toggle');
const navigation = document.querySelector('#site-navigation');
if (toggle && navigation) {
  const mobile = matchMedia('(max-width: 720px)');
  let open = false;
  const render = () => {
    toggle.hidden = !mobile.matches;
    navigation.hidden = mobile.matches && !open;
    toggle.setAttribute('aria-expanded', String(open));
  };
  toggle.addEventListener('click', () => { open = !open; render(); });
  navigation.addEventListener('click', event => {
    if (event.target.closest('a') && mobile.matches) { open = false; render(); }
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && open && mobile.matches) {
      open = false; render(); toggle.focus();
    }
  });
  mobile.addEventListener('change', () => { open = false; render(); });
  render();
}

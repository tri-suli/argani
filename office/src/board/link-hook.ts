import { ANCHOR_ATTRIBUTE, FRAGMENT_PREFIX } from '@/constants/document';
import { ANCHOR_TAG_NAME, HREF_ATTRIBUTE, LINK_REL_ATTRIBUTE, LINK_REL_VALUE, LINK_TARGET_ATTRIBUTE, LINK_TARGET_VALUE } from '@/constants/markdown';
import type { HookableSanitizer } from '@/types/markdown';

/**
 * Rendered links open in a new tab without handing the opener to the linked page. A link to an anchor of the
 * document stays in the page, marked so a click scrolls to the heading: the address hash is the route.
 */
function addLinkHook(sanitizer: HookableSanitizer): void {
  sanitizer.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName !== ANCHOR_TAG_NAME || !node.hasAttribute(HREF_ATTRIBUTE)) {
      return;
    }

    if ((node.getAttribute(HREF_ATTRIBUTE) as string).startsWith(FRAGMENT_PREFIX)) {
      node.setAttribute(ANCHOR_ATTRIBUTE, '');

      return;
    }

    node.setAttribute(LINK_TARGET_ATTRIBUTE, LINK_TARGET_VALUE);

    node.setAttribute(LINK_REL_ATTRIBUTE, LINK_REL_VALUE);
  });
}

export default addLinkHook;

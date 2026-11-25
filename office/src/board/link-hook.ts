import { ANCHOR_TAG_NAME, HREF_ATTRIBUTE, LINK_REL_ATTRIBUTE, LINK_REL_VALUE, LINK_TARGET_ATTRIBUTE, LINK_TARGET_VALUE } from '@/constants/markdown';
import type { HookableSanitizer } from '@/types/markdown';

/** Rendered links open in a new tab without handing the opener to the linked page. */
function addLinkHook(sanitizer: HookableSanitizer): void {
  sanitizer.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName === ANCHOR_TAG_NAME && node.hasAttribute(HREF_ATTRIBUTE)) {
      node.setAttribute(LINK_TARGET_ATTRIBUTE, LINK_TARGET_VALUE);

      node.setAttribute(LINK_REL_ATTRIBUTE, LINK_REL_VALUE);
    }
  });
}

export default addLinkHook;

/**
 * What the platform calls itself for a given kind of business.
 *
 * The product is always LINDA. This is only the plain-words label shown
 * beside the business name, so people can see which workspace they are in.
 */

export const PLATFORM_NAME = "LINDA";
export const PLATFORM_SLOGAN = "One Platform. Every Business.";
export const PLATFORM_OWNER = "Saccharum Technologies";

export function platformLabel(isGeneral: boolean): string {
  return isGeneral ? "Business Management Platform" : "Funeral Platform";
}

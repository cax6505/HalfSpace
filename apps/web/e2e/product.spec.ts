import { expect, test } from "@playwright/test";

test("command search streams editable filters and links results to the pitch", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  await page.keyboard.press("Control+k");
  const command = page.getByRole("textbox", { name: "Search sequences in natural language" });
  await expect(command).toBeFocused();
  await command.fill("Show sample counter-attacks into the box");
  await command.press("Enter");
  await expect(page.getByText("sample mode")).toBeVisible();
  await expect(page.getByLabel("Phase")).toHaveValue("counter-attack");
  const firstResult = page.locator(".result-card").first();
  const firstResultLabel = await firstResult.locator(".result-kicker").innerText();
  await expect(page.getByRole("heading", { name: /counter attack/i })).toBeVisible();
  await expect(page.getByLabel("Playback position").first()).toHaveAttribute("max", "23");
  await expect(page.locator(".playback-context").first()).toContainText("Opponent possession · build-up before regain");

  await page.getByLabel("team filter").fill("");
  await page.getByRole("button", { name: "Apply filters" }).click();
  const secondTeam = page.locator(".result-card").nth(1);
  await expect(secondTeam).toBeVisible();
  const secondResultLabel = await secondTeam.locator(".result-kicker").innerText();
  expect(secondResultLabel).not.toBe(firstResultLabel);
  await secondTeam.getByRole("button", { name: /counter attack/i }).click();
  await expect(page.locator(".pitch-panel-heading h2")).toContainText("counter attack");
  await expect(secondTeam).toContainText("Open sample corpus");
  await expect(page.locator(".pitch-svg [aria-label^='Player ']")).toHaveCount(22);
  await expect(page).toHaveURL(/selected=/);

  await page.locator(".result-card").first().getByRole("button", { name: "Compare" }).click();
  await secondTeam.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByRole("heading", { name: "Sequence comparison" })).toBeVisible();
  await expect(page.locator(".compare-sequence")).toHaveCount(2);
  await expect(page).toHaveURL(/compare=/);
});

test("dossier claims open an evidence drawer with a playable source", async ({ page }) => {
  await page.goto("/dossier?team=Home%20sample", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "The tactical picture" })).toBeVisible();
  await page.getByRole("button", { name: /Show agent trace/ }).click();
  await expect(page.getByRole("heading", { name: "Agent trace" })).toBeVisible();
  await page.getByRole("button", { name: /Hide agent trace/ }).click();
  await page.getByRole("button", { name: /Replay claim/ }).first().click();
  await expect(page.getByRole("complementary", { name: "Replay the claim" })).toBeVisible();
  await expect(page.getByRole("complementary").getByText("sequence:4102", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Play sequence" })).toBeVisible();
  await page.getByRole("button", { name: "Close evidence drawer" }).last().click();
  await expect(page.getByRole("complementary", { name: "Replay the claim" })).toBeHidden();
});

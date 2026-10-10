"""Pages for the framework's own checks — about:blank, no app and no network, so they stay green
in a project before its first page exists."""

from __future__ import annotations

from typing import Self

from selenium.webdriver.common.by import By

from autotests.elements import Button, CheckBox, Element, Input
from autotests.pages.base_page import BasePage


class BlankPage(BasePage):
    def url(self) -> str:
        return "about:blank"

    def is_loaded(self) -> bool:
        return self.driver.current_url == "about:blank"


class ReactQuirksPage(BlankPage):
    """What React apps do to WebDriver: a field drawn again right after it is typed into (the text
    lost), a button whose first click is ignored, a checkbox 0 px high that its cell toggles, a
    toast removed after a moment."""

    _QUIRKS = """
      document.body.innerHTML = `
        <div id="field"><input id="qty"></div>
        <button id="next">Next</button><div id="step">Define</div>
        <div id="cell" style="width:34px;height:20px">
          <label style="display:block;height:0;overflow:hidden">
            <input type="checkbox" id="box" style="width:0;height:0;margin:0"></label></div>
        <div id="toast">Saved</div>`;
      const field = document.getElementById('field');
      let drawnAgain = false;
      field.addEventListener('input', () => {
        if (!drawnAgain) {
          drawnAgain = true;
          setTimeout(() => { field.innerHTML = '<input id="qty">'; }, 50);
        }
      });
      let clicks = 0;
      document.getElementById('next').addEventListener('click', () => {
        if (++clicks > 1) document.getElementById('step').textContent = 'Specifications';
      });
      document.getElementById('cell').addEventListener('click', () => {
        const box = document.getElementById('box');
        box.checked = !box.checked;
      });
      setTimeout(() => document.getElementById('toast').remove(), 1000);
    """

    quantity = Input(By.ID, "qty")
    next_button = Button(By.ID, "next")
    box = CheckBox(By.ID, "box")
    _step = Element(By.ID, "step")
    _toast = Element(By.ID, "toast")

    def draw(self) -> Self:
        self.js(self._QUIRKS)
        return self

    def step(self) -> str:
        return self._step.text()

    def wait_toast_gone(self) -> Self:
        self._toast.wait_gone()
        return self

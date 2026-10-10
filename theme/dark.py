from __future__ import annotations

from typing import Iterable

import gradio as gr
from gradio.themes.base import Base
from gradio.themes.utils import colors, fonts, sizes


class Dark(Base):
    def __init__(
        self,
        *,
        primary_hue: colors.Color | str = colors.blue,
        secondary_hue: colors.Color | str = colors.blue,
        neutral_hue: colors.Color | str = colors.neutral,
        spacing_size: sizes.Size | str = sizes.spacing_md,
        radius_size: sizes.Size | str = sizes.radius_md,
        text_size: sizes.Size | str = sizes.text_lg,
        font: fonts.Font | str | Iterable[fonts.Font | str] = (
            fonts.GoogleFont("Syne"),
            "ui-sans-serif",
            "system-ui",
            "sans-serif",
        ),
        font_mono: fonts.Font | str | Iterable[fonts.Font | str] = (
            fonts.GoogleFont("JetBrains Mono"),
            "ui-monospace",
            "SFMono-Regular",
            "monospace",
        ),
    ):
        super().__init__(
            primary_hue=primary_hue,
            secondary_hue=secondary_hue,
            neutral_hue=neutral_hue,
            spacing_size=spacing_size,
            radius_size=radius_size,
            text_size=text_size,
            font=font,
            font_mono=font_mono,
        )

        self.name = "Dark"

        self.bg_base = "#110F0F"
        self.bg_surface = "#1A1818"
        self.bg_surface_raised = "#242121"
        self.bg_surface_hover = "#2E2A2A"
        self.bg_code = "#0B0A0A"

        self.border_subtle = "#2A2626"
        self.border_strong = "#3A3535"

        self.secondary_50 = "#eff6ff"
        self.secondary_100 = "#dbeafe"
        self.secondary_200 = "#bfdbfe"
        self.secondary_300 = "#93c5fd"
        self.secondary_400 = "#60a5fa"
        self.secondary_500 = "#3b82f6"
        self.secondary_600 = "#2563eb"
        self.secondary_700 = "#1d4ed8"
        self.secondary_800 = "#1e40af"
        self.secondary_900 = "#1e3a8a"
        self.secondary_950 = "#172554"

        self.text_primary = "#F5F5F4"
        self.text_secondary = "#A8A29E"
        self.text_muted = "#78716C"
        self.text_on_accent = "#FFFFFF"

        self.error_red = "#ef4444"
        self.success_green = "#22c55e"
        self.warning_amber = "#f59e0b"

        super().set(
            body_background_fill=self.bg_base,
            body_background_fill_dark=self.bg_base,
            background_fill_primary=self.bg_base,
            background_fill_primary_dark=self.bg_base,
            background_fill_secondary=self.bg_surface,
            background_fill_secondary_dark=self.bg_surface,

            block_background_fill=self.bg_surface,
            block_background_fill_dark=self.bg_surface,
            block_border_color="transparent",
            block_border_color_dark="transparent",
            block_border_width="0px",
            block_border_width_dark="0px",
            block_radius="*radius_md",
            block_padding="*spacing_lg",
            block_shadow="none",
            block_shadow_dark="none",

            block_info_text_color=self.text_muted,
            block_info_text_color_dark=self.text_muted,
            block_info_text_size="*text_sm",
            block_info_text_weight="400",

            block_label_background_fill=self.bg_surface_raised,
            block_label_background_fill_dark=self.bg_surface_raised,
            block_label_border_color="transparent",
            block_label_border_color_dark="transparent",
            block_label_border_width="0px",
            block_label_border_width_dark="0px",
            block_label_margin="0",
            block_label_padding="*spacing_sm *spacing_md",
            block_label_radius="*radius_md *radius_md 0 0",
            block_label_right_radius="*radius_md *radius_md 0 0",
            block_label_shadow="none",
            block_label_text_color=self.text_primary,
            block_label_text_color_dark=self.text_primary,
            block_label_text_weight="500",

            block_title_background_fill=self.bg_surface_raised,
            block_title_background_fill_dark=self.bg_surface_raised,
            block_title_border_color="transparent",
            block_title_border_color_dark="transparent",
            block_title_border_width="0px",
            block_title_padding="*spacing_sm *spacing_md",
            block_title_radius="*radius_md *radius_md 0 0",
            block_title_text_color=self.text_primary,
            block_title_text_color_dark=self.text_primary,
            block_title_text_size="*text_md",
            block_title_text_weight="600",

            body_text_color=self.text_primary,
            body_text_color_dark=self.text_primary,
            body_text_color_subdued=self.text_secondary,
            body_text_color_subdued_dark=self.text_secondary,
            body_text_size="*text_md",
            body_text_weight="400",

            border_color_accent=self.secondary_500,
            border_color_accent_dark=self.secondary_500,
            border_color_primary=self.border_subtle,
            border_color_primary_dark=self.border_subtle,

            button_border_width="1px",
            button_border_width_dark="1px",
            button_transition="0.15s ease all",
            button_large_padding="*spacing_md calc(2 * *spacing_md)",
            button_large_radius="*radius_md",
            button_large_text_size="*text_md",
            button_large_text_weight="600",
            button_small_padding="*spacing_sm calc(2 * *spacing_sm)",
            button_small_radius="*radius_sm",
            button_small_text_size="*text_sm",
            button_small_text_weight="500",

            button_primary_background_fill=self.secondary_600,
            button_primary_background_fill_dark=self.secondary_600,
            button_primary_background_fill_hover=self.secondary_500,
            button_primary_background_fill_hover_dark=self.secondary_500,
            button_primary_border_color=self.secondary_600,
            button_primary_border_color_dark=self.secondary_600,
            button_primary_border_color_hover=self.secondary_500,
            button_primary_border_color_hover_dark=self.secondary_500,
            button_primary_text_color=self.text_on_accent,
            button_primary_text_color_dark=self.text_on_accent,
            button_primary_text_color_hover=self.text_on_accent,
            button_primary_text_color_hover_dark=self.text_on_accent,

            button_secondary_background_fill="transparent",
            button_secondary_background_fill_dark="transparent",
            button_secondary_background_fill_hover=self.bg_surface_hover,
            button_secondary_background_fill_hover_dark=self.bg_surface_hover,
            button_secondary_border_color=self.border_strong,
            button_secondary_border_color_dark=self.border_strong,
            button_secondary_border_color_hover=self.secondary_500,
            button_secondary_border_color_hover_dark=self.secondary_500,
            button_secondary_text_color=self.text_primary,
            button_secondary_text_color_dark=self.text_primary,
            button_secondary_text_color_hover=self.text_primary,
            button_secondary_text_color_hover_dark=self.text_primary,

            button_cancel_background_fill="transparent",
            button_cancel_background_fill_dark="transparent",
            button_cancel_background_fill_hover=self.bg_surface_hover,
            button_cancel_background_fill_hover_dark=self.bg_surface_hover,
            button_cancel_border_color=self.border_strong,
            button_cancel_border_color_dark=self.border_strong,
            button_cancel_border_color_hover=self.border_strong,
            button_cancel_border_color_hover_dark=self.border_strong,
            button_cancel_text_color=self.text_primary,
            button_cancel_text_color_dark=self.text_primary,
            button_cancel_text_color_hover=self.text_primary,
            button_cancel_text_color_hover_dark=self.text_primary,

            input_background_fill=self.bg_code,
            input_background_fill_dark=self.bg_code,
            input_background_fill_focus=self.bg_code,
            input_background_fill_focus_dark=self.bg_code,
            input_background_fill_hover=self.bg_surface_hover,
            input_background_fill_hover_dark=self.bg_surface_hover,
            input_border_color=self.border_subtle,
            input_border_color_dark=self.border_subtle,
            input_border_color_focus=self.secondary_500,
            input_border_color_focus_dark=self.secondary_500,
            input_border_color_hover=self.border_strong,
            input_border_color_hover_dark=self.border_strong,
            input_border_width="1px",
            input_border_width_dark="1px",
            input_padding="*spacing_md",
            input_radius="*radius_md",
            input_shadow="none",
            input_shadow_dark="none",
            input_shadow_focus=f"0 0 0 3px {self.secondary_500}33",
            input_shadow_focus_dark=f"0 0 0 3px {self.secondary_500}33",
            input_placeholder_color=self.text_muted,
            input_placeholder_color_dark=self.text_muted,
            input_text_size="*text_md",
            input_text_weight="400",

            checkbox_background_color=self.bg_surface_raised,
            checkbox_background_color_dark=self.bg_surface_raised,
            checkbox_background_color_focus=self.bg_surface_raised,
            checkbox_background_color_focus_dark=self.bg_surface_raised,
            checkbox_background_color_hover=self.bg_surface_hover,
            checkbox_background_color_hover_dark=self.bg_surface_hover,
            checkbox_background_color_selected=self.secondary_600,
            checkbox_background_color_selected_dark=self.secondary_600,
            checkbox_border_color=self.border_strong,
            checkbox_border_color_dark=self.border_strong,
            checkbox_border_color_focus=self.secondary_500,
            checkbox_border_color_focus_dark=self.secondary_500,
            checkbox_border_color_hover=self.secondary_500,
            checkbox_border_color_hover_dark=self.secondary_500,
            checkbox_border_color_selected=self.secondary_600,
            checkbox_border_color_selected_dark=self.secondary_600,
            checkbox_border_radius="*radius_sm",
            checkbox_border_width="1px",
            checkbox_border_width_dark="1px",
            checkbox_shadow="none",
            checkbox_label_background_fill="transparent",
            checkbox_label_background_fill_dark="transparent",
            checkbox_label_background_fill_hover="transparent",
            checkbox_label_background_fill_hover_dark="transparent",
            checkbox_label_background_fill_selected="transparent",
            checkbox_label_background_fill_selected_dark="transparent",
            checkbox_label_border_color="transparent",
            checkbox_label_border_color_dark="transparent",
            checkbox_label_border_width="0px",
            checkbox_label_border_width_dark="0px",
            checkbox_label_gap="*spacing_md",
            checkbox_label_padding="*spacing_sm 0",
            checkbox_label_shadow="none",
            checkbox_label_text_color=self.text_primary,
            checkbox_label_text_color_dark=self.text_primary,
            checkbox_label_text_color_selected=self.text_primary,
            checkbox_label_text_color_selected_dark=self.text_primary,
            checkbox_label_text_size="*text_md",
            checkbox_label_text_weight="400",

            color_accent=self.secondary_500,
            color_accent_soft=self.bg_surface_raised,
            color_accent_soft_dark=self.bg_surface_raised,

            link_text_color=self.secondary_400,
            link_text_color_dark=self.secondary_400,
            link_text_color_hover=self.secondary_300,
            link_text_color_hover_dark=self.secondary_300,
            link_text_color_active=self.secondary_400,
            link_text_color_active_dark=self.secondary_400,
            link_text_color_visited=self.secondary_500,
            link_text_color_visited_dark=self.secondary_500,

            loader_color=self.secondary_500,
            loader_color_dark=self.secondary_500,

            slider_color=self.secondary_500,
            slider_color_dark=self.secondary_500,

            container_radius="*radius_lg",
            embed_radius="*radius_lg",
            form_gap_width="0px",
            layout_gap="*spacing_xl",

            panel_background_fill=self.bg_surface,
            panel_background_fill_dark=self.bg_surface,
            panel_border_color=self.border_subtle,
            panel_border_color_dark=self.border_subtle,
            panel_border_width="1px",
            panel_border_width_dark="1px",

            error_background_fill=self.bg_surface,
            error_background_fill_dark=self.bg_surface,
            error_border_color=self.error_red,
            error_border_color_dark=self.error_red,
            error_border_width="1px",
            error_border_width_dark="1px",
            error_text_color=self.error_red,
            error_text_color_dark=self.error_red,

            prose_header_text_weight="600",
            prose_text_size="*text_md",
            prose_text_weight="400",
            section_header_text_size="*text_md",
            section_header_text_weight="600",

            stat_background_fill=self.secondary_600,
            stat_background_fill_dark=self.secondary_600,

            table_border_color=self.border_subtle,
            table_border_color_dark=self.border_subtle,
            table_even_background_fill=self.bg_surface,
            table_even_background_fill_dark=self.bg_surface,
            table_odd_background_fill=self.bg_surface_raised,
            table_odd_background_fill_dark=self.bg_surface_raised,
            table_radius="*radius_md",
            table_row_focus=self.secondary_600,
            table_row_focus_dark=self.secondary_600,

            shadow_drop="rgba(0, 0, 0, 0.4) 0px 1px 2px 0px",
            shadow_drop_lg=(
                "0 4px 6px -1px rgba(0, 0, 0, 0.3), "
                "0 2px 4px -2px rgba(0, 0, 0, 0.3)"
            ),
            shadow_inset="rgba(0, 0, 0, 0.4) 0px 2px 4px 0px inset",
            shadow_spread="3px",
            shadow_spread_dark="3px",
        )

        self.checkbox_check = (
            "url(\"data:image/svg+xml,%3csvg viewBox='0 0 16 16' "
            "fill='white' xmlns='http://www.w3.org/2000/svg'%3e"
            "%3cpath d='M12.207 4.793a1 1 0 010 1.414l-5 5a1 1 0 "
            "01-1.414 0l-2-2a1 1 0 011.414-1.414L6.5 9.086l4.293-4.293a1 "
            "1 0 011.414 0z'/%3e%3c/svg%3e\")"
        )
        self.radio_circle = (
            "url(\"data:image/svg+xml,%3csvg viewBox='0 0 16 16' "
            "fill='white' xmlns='http://www.w3.org/2000/svg'%3e"
            "%3ccircle cx='8' cy='8' r='4'/%3e%3c/svg%3e\")"
        )

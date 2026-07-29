#!/bin/bash
# Скачивание фото упражнений (56 шт, webp-миниатюры Higgsfield CDN)
# Каждый файл сохраняется как <id>.webp рядом со скриптом.
# При ошибке одного файла — продолжаем (set -e намеренно НЕ используется).

cd "$(dirname "$0")" || exit 1

BASE="https://d8j0ntlcm91z4.cloudfront.net/user_3EYFzeIMBFYcZn6fKkhmqrweQkZ/hf_20260708"
MIN_SIZE=5120

ok=0
fail=0
failed_ids=""

download() {
  local id="$1" ts="$2" uuid="$3"
  local url="${BASE}_${ts}_${uuid}_min.webp"
  local out="${id}.webp"

  if curl -fsSL --retry 2 --connect-timeout 15 -o "$out" "$url"; then
    local size
    size=$(wc -c < "$out" | tr -d ' ')
    if [ "$size" -gt "$MIN_SIZE" ]; then
      echo "OK   $out (${size} bytes)"
      ok=$((ok+1))
      return
    else
      echo "FAIL $out — слишком маленький (${size} bytes)"
      rm -f "$out"
    fi
  else
    echo "FAIL $out — ошибка скачивания"
    rm -f "$out"
  fi
  fail=$((fail+1))
  failed_ids="$failed_ids $id"
}

while read -r id ts uuid; do
  [ -z "$id" ] && continue
  download "$id" "$ts" "$uuid"
done <<'EOF'
h_squat 125732 c55a0e43-390d-4e21-9b88-914701f38c3b
h_sumo 125734 2bc7b35f-1389-4591-817f-4be07dad3110
h_lunge 125736 10653e2f-2c69-4952-9c30-6fcea1356cb2
h_bulgarian 125738 d4b398b1-d2b4-436c-b497-d085b77b85ec
h_glute_bridge 125740 28652e7d-1fab-438f-a9d7-6fe8ba037d79
h_step_up 125742 b9259ac1-c3f7-4304-a0c0-b843ed1a6bb7
h_wall_sit 125744 ff9c5df8-b8d5-4591-8c49-68d983314d2c
h_calf 125747 253b8abf-f20b-484a-9bcd-52b47b512d8f
h_pushup 125806 96e9870f-327c-4a29-8e4a-4a707dc711ca
h_pushup_knee 125808 68a8b8dc-d411-4a8d-ab5b-0898e9579189
h_diamond 125810 be9f400c-0ff6-475a-aad7-e44ae473b737
h_dips_chair 125812 83c1a324-b51a-4ece-80c0-08711a817134
h_pike_pushup 125813 9f1d5e47-a758-4826-b692-ab59649abd08
h_band_press 125815 c75275df-daa3-4036-be63-0d54cacd0d1c
h_lateral_bottle 125817 8cdbaa68-b6e3-4ab9-82fe-6bf9c664b1a5
h_backpack_row 125820 bf3cca57-d959-4a6c-ad5f-63203688909f
h_row_band 125832 0766ae57-1434-4faa-bb3f-74aa7ab715af
h_band_pull 125834 f09bbf19-42e4-43a7-880c-c487ea871ef2
h_superman 125836 ec967b24-afdd-4fc3-886d-7b6b88c8c220
h_plank 125838 440d48fd-e19e-4e3f-b170-226f66dfa58a
h_side_plank 125839 32b576b7-95cd-4a37-b631-85053e518708
h_crunch 125841 dbdc1851-87f7-4344-aa0e-b970cf3e8988
h_leg_raise 125843 63faa2cc-7c77-436c-9ae5-2e49346c6d2b
h_deadbug 125846 01746c49-390a-4999-a3ed-92bbbca12dd2
h_bird_dog 125859 a723e51c-f548-493e-8ff7-996a5a901bae
h_mountain 125901 44a6a0df-060c-4cd4-8859-5e74af709be0
h_jumping_jacks 125903 82c44216-815c-4826-be6d-565ce7c36cf0
h_burpee 125906 0f91c0b0-b16a-4f94-9ac6-d5fd005f5d6e
g_squat 125909 163daeee-4121-4b2f-a692-834466f8648b
g_leg_press 125911 76e9b888-11a9-44af-8259-0645fcdad0e3
g_rdl 125913 65a515c8-c3c2-480f-9320-5a490a5279d9
g_hip_thrust 125914 b5446811-5695-43f2-988e-456b2b41f352
g_leg_curl 125926 20c6b2fc-da0c-4808-833c-f4485157b5d6
g_leg_ext 125928 5c45be54-af37-4bbc-ad46-ca1e760e9f63
g_abduction 125931 ff07b2fe-5ad8-4e3f-ba01-5d426a3befbb
g_calf_press 125932 91dd28b1-1db0-4115-afc2-1eacbf115f64
g_bench 125935 741bf06f-c5d1-4b7b-9fa1-6a721755df4b
g_db_press 125937 2139a08f-94c0-4917-b4f9-1d2da2793580
g_incline_db 125939 529fb249-1e4a-4160-ad4e-35febb717ac6
g_cable_fly 125941 b04de907-6371-4924-a333-fbf9953ca06d
g_lat_pulldown 125951 d9cb31c9-ed6d-4ff1-a18b-2473f8ae48c2
g_pullup 125953 6f59ecfb-0487-4aa0-8e17-3164d7f58ecb
g_row_cable 125955 21aadc1b-f5e2-45af-b647-fc0aab62a524
g_db_row 125958 e875f44c-5cc7-4e2f-a3fe-e9b162992818
g_hyperext 125959 da66ebf3-57c2-402b-8ff8-ac69933b4029
g_ohp 130001 3cc6c652-8b93-4b7d-bfce-000ecf557cf9
g_lateral 130003 db8c6c51-7c77-4039-bd03-0b58eaebc808
g_face_pull 130006 29b19daf-6a71-480d-9d43-1222b3901d3a
g_curl 130028 4a5fdd32-9633-4ca7-8f42-c3e394a303b8
g_hammer 130029 ef013cd7-3e4b-434a-99e9-dedb6425f70f
g_triceps_rope 130032 438945e0-a065-4a7c-be1f-4d3cc77be15c
g_cable_crunch 130034 8cade698-96df-4f30-961e-5f35c4522cf4
g_hanging_knee 130036 502f0c4b-673b-441c-84c9-485113d073b1
g_plank_w 130038 345f9f52-155a-4374-a0e9-d7737f3b1eb2
g_treadmill 130040 ba469c34-1c4b-4b36-a3cc-0f32cc251ad3
g_bike 130041 9315159a-f034-4e20-9ae6-a7bf11a98502
EOF

echo ""
echo "Готово: скачано $ok, ошибок $fail"
[ -n "$failed_ids" ] && echo "Не скачались:$failed_ids"
